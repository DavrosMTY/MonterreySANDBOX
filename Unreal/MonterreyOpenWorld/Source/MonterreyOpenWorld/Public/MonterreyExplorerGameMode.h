#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "MonterreyExplorerGameMode.generated.h"

UCLASS()
class MONTERREYOPENWORLD_API AMonterreyExplorerGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    AMonterreyExplorerGameMode();
    virtual void StartPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void RestartPlayer(AController* Player) override;
    virtual AActor* ChoosePlayerStart_Implementation(AController* Player) override;
private:
    bool bSmoke = false;
    bool bFinished = false;
    bool bWalking = false;
    float SmokeTime = 0.f;
    float MoveTime = 0.f;
    double WalkDistance = 0.;
    double RunDistance = 0.;
    FVector PhaseStart = FVector::ZeroVector;
    void FinishSmoke(bool bPassed, const FString& Reason);
};
