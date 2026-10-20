#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Engine/DataTable.h"
#include "MonterreyGeoLibrary.generated.h"

class UStaticMesh;

USTRUCT(BlueprintType)
struct MONTERREYGEOEDITOR_API FMonterreyBuildingRow : public FTableRowBase
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString SourceId;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FVector PositionCm = FVector::ZeroVector;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FVector SizeCm = FVector::ZeroVector;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString BuildingClass;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) double HeightM = 0.;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool HeightEstimated = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FString HeightSource;
};

/** Prepared against UE 5.6 API documentation; compilation/editor QA remain required. */
UCLASS()
class MONTERREYGEOEDITOR_API UMonterreyGeoLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
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
