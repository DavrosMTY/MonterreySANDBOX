#pragma once
#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "MonterreyExplorerHUD.generated.h"

UCLASS()
class MONTERREYOPENWORLD_API AMonterreyExplorerHUD : public AHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
};
