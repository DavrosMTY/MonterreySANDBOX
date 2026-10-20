"""Report actual editor availability. Never equate a project descriptor with a build."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil


def inspect_environment():
    root = Path(__file__).resolve().parents[1]
    candidates = [os.environ.get('UE_EDITOR')]
    candidates += [shutil.which(name) for name in ('UnrealEditor-Cmd.exe', 'UnrealEditor.exe', 'UnrealEditor-Cmd', 'UnrealEditor')]
    candidates += [str(p) for pattern in ('/opt/unreal*/Engine/Binaries/Linux/UnrealEditor', '/workspace/UnrealEngine/Engine/Binaries/Linux/UnrealEditor')
                   for p in Path('/').glob(pattern.lstrip('/'))]
    editor = next((str(Path(p).resolve()) for p in candidates if p and Path(p).is_file()), None)
    project = root/'Unreal/MonterreyOpenWorld/MonterreyOpenWorld.uproject'
    descriptor = json.loads(project.read_text(encoding='utf-8'))
    return {'host_platform': platform.system(), 'target_platform': 'Windows PC', 'editor': editor,
            'project_descriptor_valid_json': descriptor.get('FileVersion') == 3,
            'engine_executed': False, 'project_compiled': False, 'landscape_import_verified': False,
            'status': 'editor_detected_not_validated' if editor else 'blocked_no_unreal_editor',
            'next_requirement': 'Licensed UE5 editor and Windows build environment for target validation'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    args = parser.parse_args()
    result = inspect_environment()
    if args.output:
        target = Path(args.output); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['editor'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
