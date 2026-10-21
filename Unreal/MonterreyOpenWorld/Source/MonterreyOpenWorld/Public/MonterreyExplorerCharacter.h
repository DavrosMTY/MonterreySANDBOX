#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "MonterreyExplorerCharacter.generated.h"

class UCameraComponent;
class USpringArmComponent;

/** Native placeholder body: no dependency on StarterContent or licensed mannequin. */
UCLASS()
class MONTERREYOPENWORLD_API AMonterreyExplorerCharacter : public ACharacter
{
    GENERATED_BODY()
public:
    AMonterreyExplorerCharacter();
    virtual void SetupPlayerInputComponent(UInputComponent* Input) override;
    void SetRunning(bool bRunning);
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<USpringArmComponent> CameraBoom;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<UCameraComponent> FollowCamera;
private:
    void Forward(float Value);
    void Right(float Value);
    void Turn(float Value);
    void Look(float Value);
    void RunPressed();
    void RunReleased();
};
