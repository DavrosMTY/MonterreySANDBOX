"""Final editor receipt after WorldPartitionConvertCommandlet; not yet executed."""
import json
import os
from pathlib import Path
import unreal

receipt = Path(os.environ['MOW_UE_RECEIPT'])
result = json.loads(receipt.read_text(encoding='utf-8'))
try:
    target = os.environ['MOW_MAP_PATH']+'_WP'
    if unreal.EditorLoadingAndSavingUtils.load_map(target) is None:
        raise RuntimeError('Converted map cannot be loaded')
    if not unreal.MonterreyGeoLibrary.is_world_partition_enabled():
        raise RuntimeError('Converted world has no WorldPartition')
    result.update(status='editor_import_and_partition_verified',converted_map=target,world_partition_validated=True)
except Exception as exc:
    result.update(status='failed',error=str(exc)); raise
finally:
    receipt.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
