#include "MonterreyGeoLibrary.h"
#include "Editor.h"
#include "Editor/EditorEngine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Landscape.h"
#include "LandscapeEdit.h"
#include "LandscapeInfo.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Modules/ModuleManager.h"
#include "Engine/StaticMesh.h"
#include "PhysicsEngine/BodySetup.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"
#include "MonterreySectorMetadata.h"

IMPLEMENT_MODULE(FDefaultModuleImpl, MonterreyGeoEditor)

bool UMonterreyGeoLibrary::SetSectorProvenance(UStaticMesh* Mesh, const FString& ProvenanceJSON)
{
    TSharedPtr<FJsonObject> Parsed;
    if (!Mesh || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(ProvenanceJSON), Parsed)) return false;
    Mesh->Modify();
    auto* Data = NewObject<UMonterreySectorMetadata>(Mesh);
    Data->ProvenanceJSON = ProvenanceJSON;
    Mesh->AddAssetUserData(Data);
    Mesh->MarkPackageDirty();
    return true;
}

FString UMonterreyGeoLibrary::FindExplorerSpawn(const FString& CandidatesPath)
{
    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    FString Text;
    TSharedPtr<FJsonObject> Root;
    if (!World || !FFileHelper::LoadFileToString(Text, *CandidatesPath) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
        return TEXT("{\"passed\":false,\"reason\":\"no_world_or_candidates\"}");
    FCollisionQueryParams Params(SCENE_QUERY_STAT(UE001Spawn), true);
    int32 Index = 0;
    for (const auto& Value : Root->GetArrayField(TEXT("probes")))
    {
        const auto& P = Value->AsObject()->GetArrayField(TEXT("position_unreal_cm"));
        if (P.Num() != 3) { ++Index; continue; }
        const FVector Expected(P[0]->AsNumber(), P[1]->AsNumber(), P[2]->AsNumber());
        FHitResult Hit;
        if (World->LineTraceSingleByChannel(Hit, Expected + FVector(0, 0, 100),
            Expected - FVector(0, 0, 50), ECC_Visibility, Params) &&
            FMath::Abs(Hit.ImpactPoint.Z - Expected.Z) <= 8. && Hit.ImpactNormal.Z >= .7f)
        {
            const FVector Centre = Hit.ImpactPoint + FVector(0, 0, 91);
            if (!World->OverlapBlockingTestByChannel(Centre, FQuat::Identity, ECC_Pawn,
                FCollisionShape::MakeCapsule(34.f, 88.f), Params))
                return FString::Printf(TEXT("{\"passed\":true,\"candidate_index\":%d,\"capsule_overlap_checked\":true,\"position_unreal_cm\":[%.9f,%.9f,%.9f]}"), Index, Centre.X, Centre.Y, Centre.Z);
        }
        ++Index;
    }
    return TEXT("{\"passed\":false,\"reason\":\"no_collision_validated_spawn\"}");
}

bool UMonterreyGeoLibrary::ConfigureStaticWorldCollision(UStaticMesh* Mesh)
{
    if (!Mesh) return false;
    Mesh->Modify();
    Mesh->CreateBodySetup();
    UBodySetup* Body = Mesh->GetBodySetup();
    if (!Body) return false;
    Body->Modify();
    Body->CollisionTraceFlag = CTF_UseComplexAsSimple;
    Body->bDoubleSidedGeometry = true;
    Body->InvalidatePhysicsData();
    Body->CreatePhysicsMeshes();
    Mesh->MarkPackageDirty();
    // This is configuration evidence only; runtime traces remain mandatory.
    return Body->CollisionTraceFlag == CTF_UseComplexAsSimple;
}

FString UMonterreyGeoLibrary::ValidateWorldProbes(const FString& ProbesPath)
{
    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    FString Text;
    TSharedPtr<FJsonObject> Root;
    if (!World || !FFileHelper::LoadFileToString(Text, *ProbesPath) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
        return TEXT("{\"passed\":false,\"reason\":\"no_world_or_probe_file\"}");
    int32 Checked = 0, Failed = 0;
    double MaxError = 0.;
    const double Tolerance = Root->GetNumberField(TEXT("expected_surface_tolerance_cm"));
    FCollisionQueryParams Params(SCENE_QUERY_STAT(WORLD001Probe), true);
    for (const TSharedPtr<FJsonValue>& Value : Root->GetArrayField(TEXT("probes")))
    {
        const auto& P = Value->AsObject()->GetArrayField(TEXT("position_unreal_cm"));
        if (P.Num() != 3) { ++Failed; continue; }
        const FVector Expected(P[0]->AsNumber(), P[1]->AsNumber(), P[2]->AsNumber());
        FHitResult Hit;
        const bool bHit = World->LineTraceSingleByChannel(Hit, Expected + FVector(0, 0, 100.),
            Expected - FVector(0, 0, 50.), ECC_Visibility, Params);
        const double Error = bHit ? FMath::Abs(Hit.ImpactPoint.Z - Expected.Z) : 1.e9;
        MaxError = FMath::Max(MaxError, Error);
        if (!bHit || Error > Tolerance) ++Failed;
        ++Checked;
    }
    return FString::Printf(TEXT("{\"passed\":%s,\"traces\":%d,\"failed\":%d,\"max_z_error_cm\":%.9f,\"capsule_sweep_executed\":false}"),
        Checked > 0 && Failed == 0 ? TEXT("true") : TEXT("false"), Checked, Failed, MaxError);
}

namespace
{
TSharedPtr<FJsonObject> ReadManifest(const FString& Directory)
{
    FString Text;
    TSharedPtr<FJsonObject> Root;
    if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(Directory, TEXT("manifest.json"))) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
    {
        return nullptr;
    }
    return Root;
}

FVector JsonVector(const TArray<TSharedPtr<FJsonValue>>& Values)
{
    return FVector(Values[0]->AsNumber(), Values[1]->AsNumber(), Values[2]->AsNumber());
}

FString Label(int32 X, int32 Y)
{
    return FString::Printf(TEXT("GEO002_Landscape_%d_%d"), X, Y);
}
}

int32 UMonterreyGeoLibrary::ImportLandscape(const FString& TerrainDirectory)
{
    const TSharedPtr<FJsonObject> Root = ReadManifest(TerrainDirectory);
    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!Root.IsValid() || !World || Root->GetNumberField(TEXT("schema_version")) != 3)
    {
        UE_LOG(LogTemp, Error, TEXT("GEO002: missing editor world or invalid terrain manifest"));
        return -1;
    }
    const FVector Scale(Root->GetNumberField(TEXT("unreal_x_scale_cm")),
                        Root->GetNumberField(TEXT("unreal_y_scale_cm")),
                        Root->GetNumberField(TEXT("unreal_z_scale_cm")));
    int32 Count = 0;
    for (const TSharedPtr<FJsonValue>& Value : Root->GetArrayField(TEXT("tiles")))
    {
        const TSharedPtr<FJsonObject> Tile = Value->AsObject();
        const FString Filename = Tile->GetStringField(TEXT("r16"));
        if (FPaths::GetCleanFilename(Filename) != Filename || !Filename.EndsWith(TEXT(".r16"))) return -1;
        TArray<uint8> Bytes;
        const FString Path = FPaths::Combine(TerrainDirectory, Filename);
        if (!FFileHelper::LoadFileToArray(Bytes, *Path) || Bytes.Num() != 505 * 505 * 2) return -1;
        TArray<uint16> Heights;
        Heights.SetNumUninitialized(505 * 505);
        for (int32 I = 0; I < Heights.Num(); ++I)
        {
            Heights[I] = static_cast<uint16>(Bytes[2 * I]) | (static_cast<uint16>(Bytes[2 * I + 1]) << 8);
        }
        ALandscape* Landscape = World->SpawnActor<ALandscape>();
        if (!Landscape) return -1;
        Landscape->SetActorLabel(Label(Tile->GetIntegerField(TEXT("x")), Tile->GetIntegerField(TEXT("y"))));
        Landscape->SetActorTransform(FTransform(FRotator::ZeroRotator,
            JsonVector(Tile->GetArrayField(TEXT("actor_location_cm"))), Scale));
        TMap<FGuid, TArray<uint16>> HeightData;
        HeightData.Add(FGuid(), MoveTemp(Heights));
        TMap<FGuid, TArray<FLandscapeImportLayerInfo>> Layers;
        Layers.Add(FGuid(), TArray<FLandscapeImportLayerInfo>());
        // UE 5.6 documented ALandscapeProxy::Import pointer overload.
        Landscape->Import(FGuid::NewGuid(), 0, 0, 504, 504, 2, 63, HeightData,
            *Path, Layers, ELandscapeImportAlphamapType::Additive,
            static_cast<const TArray<FLandscapeLayer>*>(nullptr));
        if (!Landscape->GetLandscapeInfo()) return -1;
        Landscape->MarkPackageDirty();
        ++Count;
    }
    return Count;
}

bool UMonterreyGeoLibrary::IsWorldPartitionEnabled()
{
    const UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    return World && World->GetWorldPartition() != nullptr;
}

FString UMonterreyGeoLibrary::ValidateLandscapeControls(const FString& TerrainDirectory)
{
    const TSharedPtr<FJsonObject> Root = ReadManifest(TerrainDirectory);
    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!Root.IsValid() || !World) return TEXT("{\"passed\":false,\"reason\":\"no_world_or_manifest\"}");
    int32 Verified = 0;
    double MaxError = 0.;
    for (const TSharedPtr<FJsonValue>& Value : Root->GetArrayField(TEXT("tiles")))
    {
        const TSharedPtr<FJsonObject> Tile = Value->AsObject();
        const FString ExpectedLabel = Label(Tile->GetIntegerField(TEXT("x")), Tile->GetIntegerField(TEXT("y")));
        ALandscape* Landscape = nullptr;
        for (TActorIterator<ALandscape> It(World); It; ++It)
        {
            if (It->GetActorLabel() == ExpectedLabel) { Landscape = *It; break; }
        }
        if (!Landscape || !Landscape->GetLandscapeInfo()) return TEXT("{\"passed\":false,\"reason\":\"landscape_missing\"}");
        FLandscapeEditDataInterface Edit(Landscape->GetLandscapeInfo());
        const auto& Points = Tile->GetArrayField(TEXT("control_points"));
        for (int32 I = 0; I < 4; ++I)
        {
            const int32 X = I % 2 ? 504 : 0;
            const int32 Y = I >= 2 ? 504 : 0;
            uint16 Height = 0;
            Edit.GetHeightDataFast(X, Y, X, Y, &Height, 0);
            const FVector Actual = Landscape->GetActorTransform().TransformPosition(
                FVector(X, Y, (static_cast<double>(Height) - 32768.) / 128.));
            const FVector Expected = JsonVector(Points[I]->AsObject()->GetArrayField(TEXT("unreal_cm")));
            MaxError = FMath::Max(MaxError, FVector::Distance(Actual, Expected));
            ++Verified;
        }
    }
    return FString::Printf(TEXT("{\"passed\":%s,\"control_points\":%d,\"max_error_cm\":%.9f}"),
        MaxError <= 0.2 ? TEXT("true") : TEXT("false"), Verified, MaxError);
}
