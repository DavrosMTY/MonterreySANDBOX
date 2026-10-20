#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "MonterreyWorldData.generated.h"

/** Serialized coordinate contract; no automatic geographic/datum conversions. */
UCLASS(BlueprintType)
class MONTERREYOPENWORLD_API UMonterreyWorldData : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FString Revision;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FString ModelSHA256;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) int32 HorizontalEPSG = 32614;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FVector2D ProjectedCenterMetres = FVector2D::ZeroVector;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FString VerticalDatum;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) double UnrealUnitsPerGridMetre = 100.;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) bool ProceduralElevationCorrections = true;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) bool RuntimeTraversalValidated = false;
};
