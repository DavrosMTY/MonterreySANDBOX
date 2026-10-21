using UnrealBuildTool;
public class MonterreyOpenWorld : ModuleRules
{
    public MonterreyOpenWorld(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine" });
    }
}
