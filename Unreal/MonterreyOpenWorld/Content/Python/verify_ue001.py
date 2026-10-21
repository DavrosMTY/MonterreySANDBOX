"""Real editor map/WP validation; movement is tested separately in a game process."""
import json
import os
from pathlib import Path
import unreal

receipt=Path(os.environ['MOW_UE_RECEIPT'])
result=json.loads(receipt.read_text(encoding='utf-8'))
try:
    target=os.environ['MOW_MAP_PATH']+'_WP'
    if unreal.EditorLoadingAndSavingUtils.load_map(target) is None:raise RuntimeError('Converted map did not load')
    if not unreal.MonterreyGeoLibrary.is_world_partition_enabled():raise RuntimeError('No World Partition')
    result.update(status='ue001_map_loaded_pending_play',converted_map=target,world_partition_validated=True)
except Exception as exc:
    result.update(status='failed',error=str(exc));raise
finally:
    receipt.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
