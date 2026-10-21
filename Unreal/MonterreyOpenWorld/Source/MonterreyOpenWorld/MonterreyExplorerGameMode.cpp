#include "MonterreyExplorerGameMode.h"
#include "MonterreyExplorerCharacter.h"
#include "MonterreyExplorerHUD.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/PlayerStart.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "EngineUtils.h"
#include "TimerManager.h"
#include "Dom/JsonObject.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "CollisionQueryParams.h"
#include "Misc/CommandLine.h"
#include "Misc/EngineVersion.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "HAL/PlatformMisc.h"
#include "Serialization/JsonSerializer.h"
#include "UnrealClient.h"

AMonterreyExplorerGameMode::AMonterreyExplorerGameMode()
{
    DefaultPawnClass = AMonterreyExplorerCharacter::StaticClass();
    HUDClass = AMonterreyExplorerHUD::StaticClass();
    PrimaryActorTick.bCanEverTick = true;
}
AActor* AMonterreyExplorerGameMode::ChoosePlayerStart_Implementation(AController* Player)
{
    for (TActorIterator<APlayerStart> It(GetWorld()); It; ++It)
        if (It->ActorHasTag(TEXT("UE001_SafeSpawn"))) return *It;
    return nullptr; // Never spawn at world origin/under the georeferenced city.
}
void AMonterreyExplorerGameMode::RestartPlayer(AController* Player)
{
    AActor* Start = ChoosePlayerStart(Player);
    if (!Start) return;
    FHitResult Hit;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(UE001SpawnFloor), true);
    const FVector P = Start->GetActorLocation();
    if (!GetWorld()->LineTraceSingleByChannel(Hit, P, P - FVector(0, 0, 110), ECC_Visibility, Params) || Hit.ImpactNormal.Z < .7f) return;
    if (GetWorld()->OverlapBlockingTestByChannel(P, FQuat::Identity, ECC_Pawn,
        FCollisionShape::MakeCapsule(34.f, 88.f), Params)) return;
    Super::RestartPlayer(Player);
}
void AMonterreyExplorerGameMode::StartPlay()
{
    Super::StartPlay();
    bSmoke = FParse::Param(FCommandLine::Get(), TEXT("UE001Smoke"));
    if (bSmoke && FParse::Param(FCommandLine::Get(), TEXT("nullrhi")))
        FinishSmoke(false, TEXT("NullRHI cannot certify visual exploration"));
}
void AMonterreyExplorerGameMode::Tick(float Delta)
{
    Super::Tick(Delta);
    APlayerController* PC = GetWorld()->GetFirstPlayerController();
    if (PC && !PC->GetPawn()) RestartPlayer(PC); // Retry while WP cells acquire collision.
    if (!bSmoke || bFinished) return;
    SmokeTime += Delta;
    auto* Pawn = PC ? Cast<AMonterreyExplorerCharacter>(PC->GetPawn()) : nullptr;
    if (SmokeTime > 35.f) { FinishSmoke(false, TEXT("Spawn, floor or movement timeout")); return; }
    if (!Pawn || !Pawn->GetCharacterMovement()->IsMovingOnGround()) return;
    if (!bWalking)
    {
        bWalking = true;
        PhaseStart = Pawn->GetActorLocation();
    }
    MoveTime += Delta;
    if (MoveTime <= .5f)
        Pawn->AddMovementInput(Pawn->GetActorForwardVector(), 1.f);
    else if (MoveTime <= 1.f)
    {
        if (WalkDistance == 0.)
        {
            WalkDistance = FVector::Dist2D(PhaseStart, Pawn->GetActorLocation());
            PhaseStart = Pawn->GetActorLocation();
        }
        Pawn->SetRunning(true);
        Pawn->AddMovementInput(Pawn->GetActorForwardVector(), 1.f);
    }
    else
    {
        RunDistance = FVector::Dist2D(PhaseStart, Pawn->GetActorLocation());
        const bool bCamera = Pawn->FollowCamera && Pawn->FollowCamera->IsActive() && PC->GetViewTarget() == Pawn;
        FinishSmoke(WalkDistance > 50. && RunDistance > 80. && bCamera && GetWorld()->GetWorldPartition(),
            TEXT("Short native movement/floor/camera smoke; not full-sector traversal certification"));
    }
}
void AMonterreyExplorerGameMode::FinishSmoke(bool bPassed, const FString& Reason)
{
    if (bFinished) return;
    bFinished = true;
    FString Receipt, RunId, Screenshot;
    FParse::Value(FCommandLine::Get(), TEXT("UE001Receipt="), Receipt);
    FParse::Value(FCommandLine::Get(), TEXT("UE001RunId="), RunId);
    FParse::Value(FCommandLine::Get(), TEXT("UE001Screenshot="), Screenshot);
    auto Root = MakeShared<FJsonObject>();
    Root->SetStringField(TEXT("status"), bPassed ? TEXT("passed") : TEXT("failed"));
    Root->SetStringField(TEXT("run_id"), RunId);
    Root->SetStringField(TEXT("engine_version"), FEngineVersion::Current().ToString());
    Root->SetStringField(TEXT("map"), GetWorld()->GetMapName());
    Root->SetStringField(TEXT("reason"), Reason);
    Root->SetBoolField(TEXT("world_partition"), GetWorld()->GetWorldPartition() != nullptr);
    Root->SetBoolField(TEXT("render_viewport"), GEngine && GEngine->GameViewport && GEngine->GameViewport->Viewport);
    Root->SetNumberField(TEXT("walk_distance_cm"), WalkDistance);
    Root->SetNumberField(TEXT("run_distance_cm"), RunDistance);
    FString Text;
    FJsonSerializer::Serialize(Root, TJsonWriterFactory<>::Create(&Text));
    if (!Receipt.IsEmpty()) FFileHelper::SaveStringToFile(Text, *Receipt);
    if (bPassed && !Screenshot.IsEmpty()) FScreenshotRequest::RequestScreenshot(Screenshot, false, false);
    // Exit on a subsequent tick so the rendered screenshot can be written.
    FTimerHandle ExitTimer;
    GetWorldTimerManager().SetTimer(ExitTimer, [] { FPlatformMisc::RequestExit(false); }, 2.f, false);
}
