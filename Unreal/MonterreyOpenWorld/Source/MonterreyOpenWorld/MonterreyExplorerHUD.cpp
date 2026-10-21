#include "MonterreyExplorerHUD.h"

void AMonterreyExplorerHUD::DrawHUD()
{
    Super::DrawHUD();
    DrawText(TEXT("Monterrey Open World"), FLinearColor::White, 24.f, 24.f);
    DrawText(TEXT("WASD: mover   Mouse: camara   Shift: correr   Espacio: saltar"), FLinearColor::White, 24.f, 48.f);
}
