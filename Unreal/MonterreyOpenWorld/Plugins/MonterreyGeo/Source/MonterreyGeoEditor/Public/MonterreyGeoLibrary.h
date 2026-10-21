#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Engine/DataTable.h"
#include "MonterreyGeoLibrary.generated.h"

class UStaticMesh;

/** Prepared against UE 5.6 API documentation; compilation/editor QA remain required. */
UCLASS()
class MONTERREYGEOEDITOR_API UMonterreyGeoLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Serialized runtime user data, retained when cooking sector meshes. */
    UFUNCTION(BlueprintCallable, Category="Monterrey|World")
    static bool SetSectorProvenance(UStaticMesh* Mesh, const FString& ProvenanceJSON);

    /** Vertical ray plus capsule overlap; valid only after this code runs in UE. */
    UFUNCTION(BlueprintCallable, Category="Monterrey|World")
    static FString FindExplorerSpawn(const FString& CandidatesPath);

    /** Static environment only. Nanite rendering does not validate collision. */
    UFUNCTION(BlueprintCallable, Category="Monterrey|World")
    static bool ConfigureStaticWorldCollision(UStaticMesh* Mesh);

    /** Vertical visibility traces only; does not certify wheel/capsule traversal. */
    UFUNCTION(BlueprintCallable, Category="Monterrey|World")
    static FString ValidateWorldProbes(const FString& ProbesPath);

    UFUNCTION(BlueprintCallable, Category="Monterrey|Geo")
    static int32 ImportLandscape(const FString& TerrainDirectory);

    UFUNCTION(BlueprintCallable, Category="Monterrey|Geo")
    static bool IsWorldPartitionEnabled();

    UFUNCTION(BlueprintCallable, Category="Monterrey|Geo")
    static FString ValidateLandscapeControls(const FString& TerrainDirectory);
};
