#pragma once
#include "CoreMinimal.h"
#include "Engine/AssetUserData.h"
#include "MonterreySectorMetadata.generated.h"

/** Cooked with each mesh; contains original IDs, cell, datum, input hashes and transform. */
UCLASS()
class MONTERREYOPENWORLD_API UMonterreySectorMetadata : public UAssetUserData
{
    GENERATED_BODY()
public:
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) FString ProvenanceJSON;
};
