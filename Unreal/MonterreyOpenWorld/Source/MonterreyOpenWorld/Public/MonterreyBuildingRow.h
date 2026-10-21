#pragma once
#include "CoreMinimal.h"
#include "Engine/DataTable.h"
#include "MonterreyBuildingRow.generated.h"

USTRUCT(BlueprintType)
struct MONTERREYOPENWORLD_API FMonterreyBuildingRow : public FTableRowBase
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
