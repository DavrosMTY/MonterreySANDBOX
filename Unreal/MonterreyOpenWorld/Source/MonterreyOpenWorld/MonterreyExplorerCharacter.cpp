#include "MonterreyExplorerCharacter.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Controller.h"
#include "GameFramework/SpringArmComponent.h"
#include "UObject/ConstructorHelpers.h"

AMonterreyExplorerCharacter::AMonterreyExplorerCharacter()
{
    GetCapsuleComponent()->InitCapsuleSize(34.f, 88.f);
    bUseControllerRotationYaw = false;
    GetCharacterMovement()->bOrientRotationToMovement = true;
    GetCharacterMovement()->RotationRate = FRotator(0.f, 540.f, 0.f);
    GetCharacterMovement()->MaxWalkSpeed = 400.f;
    GetCharacterMovement()->JumpZVelocity = 420.f;
    GetCharacterMovement()->AirControl = .2f;
    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
    CameraBoom->SetupAttachment(RootComponent);
    CameraBoom->TargetArmLength = 350.f;
    CameraBoom->SocketOffset = FVector(0.f, 40.f, 60.f);
    CameraBoom->bUsePawnControlRotation = true;
    FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
    FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    UStaticMeshComponent* Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PlaceholderBody"));
    Body->SetupAttachment(RootComponent);
    Body->SetStaticMesh(Cylinder.Object);
    Body->SetRelativeLocation(FVector(0.f, 0.f, -15.f));
    Body->SetRelativeScale3D(FVector(.5f, .5f, 1.3f));
    Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void AMonterreyExplorerCharacter::SetupPlayerInputComponent(UInputComponent* Input)
{
    Super::SetupPlayerInputComponent(Input);
    Input->BindAxis(TEXT("MoveForward"), this, &AMonterreyExplorerCharacter::Forward);
    Input->BindAxis(TEXT("MoveRight"), this, &AMonterreyExplorerCharacter::Right);
    Input->BindAxis(TEXT("Turn"), this, &AMonterreyExplorerCharacter::Turn);
    Input->BindAxis(TEXT("LookUp"), this, &AMonterreyExplorerCharacter::Look);
    Input->BindAction(TEXT("Jump"), IE_Pressed, this, &ACharacter::Jump);
    Input->BindAction(TEXT("Jump"), IE_Released, this, &ACharacter::StopJumping);
    Input->BindAction(TEXT("Run"), IE_Pressed, this, &AMonterreyExplorerCharacter::RunPressed);
    Input->BindAction(TEXT("Run"), IE_Released, this, &AMonterreyExplorerCharacter::RunReleased);
}
void AMonterreyExplorerCharacter::Forward(float Value)
{
    if (Controller) AddMovementInput(FRotationMatrix(FRotator(0, Controller->GetControlRotation().Yaw, 0)).GetUnitAxis(EAxis::X), Value);
}
void AMonterreyExplorerCharacter::Right(float Value)
{
    if (Controller) AddMovementInput(FRotationMatrix(FRotator(0, Controller->GetControlRotation().Yaw, 0)).GetUnitAxis(EAxis::Y), Value);
}
void AMonterreyExplorerCharacter::Turn(float Value) { AddControllerYawInput(Value); }
void AMonterreyExplorerCharacter::Look(float Value) { AddControllerPitchInput(Value); }
void AMonterreyExplorerCharacter::SetRunning(bool bRunning) { GetCharacterMovement()->MaxWalkSpeed = bRunning ? 650.f : 400.f; }
void AMonterreyExplorerCharacter::RunPressed() { SetRunning(true); }
void AMonterreyExplorerCharacter::RunReleased() { SetRunning(false); }
