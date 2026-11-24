import os,json,socket
os.environ['HF_HUB_OFFLINE']='1';os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
from ai_runtime import LocalAI
from matching import AIMatchingService
from seed import sample_image
from pathlib import Path
from unittest.mock import patch
from datetime import date
import tempfile
with tempfile.TemporaryDirectory() as folder:
 p=Path(folder)/'bag.png';p.write_bytes(sample_image())
 with patch('socket.socket.connect',side_effect=RuntimeError('Network is forbidden during inference')):
  engine=LocalAI();assert engine.prepare(),engine.reason
  model=AIMatchingService(engine.adapter,engine.weights,engine.photo_adapter)
  r=dict(category='bags',description='a dark green backpack',color='green',brand='Campus',place='Library',date_lost=date.today().isoformat())
  i=dict(r,date_found=date.today().isoformat(),photo_path=str(p))
  without=model.explain(r,i)
  with_photo=model.explain(dict(r,photo_path=str(p)),i)
  assert with_photo['total']>99.9
  assert without['photo_source']=='owner_description'
  assert without['photo_model']=='CLIP'
  assert with_photo['photo_model']==('DINOv2' if engine.photo_adapter else 'CLIP')
  print(json.dumps({'runtime':engine.status(),'no_owner_photo':without,'with_owner_photo':with_photo},indent=2))
