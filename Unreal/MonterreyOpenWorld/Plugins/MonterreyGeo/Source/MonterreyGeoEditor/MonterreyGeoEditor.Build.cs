using UnrealBuildTool;

public class MonterreyGeoEditor : ModuleRules
{
    public MonterreyGeoEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine" });
        PrivateDependencyModuleNames.AddRange(new[] { "UnrealEd", "Landscape", "Json", "JsonUtilities", "PhysicsCore" });
    }
}
