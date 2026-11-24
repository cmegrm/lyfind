"""Explicit first-time download. Inference itself never uses a remote service."""
import os
import shutil
import tempfile
from math import isfinite
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL_REVISION = '327ab6726d33c0e22f920c83f2ff9e4bd38ca37f'
DINO_REVISION = 'ed25f3a31f01632728cabb09d1542f84ab7b0056'

def verify_model(adapter):
    from PIL import Image

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'setup-check.png'
        Image.new('RGB', (32, 32), 'darkgreen').save(path)
        text = adapter.embed_text('a dark green backpack')
        photo = adapter.embed_image(path)
    if not text or len(text) != len(photo) or not all(isfinite(value) for value in text + photo):
        raise RuntimeError('The local model could not produce valid text and photo embeddings.')
    print('Local text and photo matching passed.', flush=True)


def prepare_clip():
    from matching import ClipAdapter
    from sentence_transformers import SentenceTransformer

    target = ROOT/'models'/'clip-ViT-B-32'
    if (target/'modules.json').exists():
        print('Local model already exists. Verifying it offline...', flush=True)
        model = SentenceTransformer(str(target), device='cpu', local_files_only=True, trust_remote_code=False)
        verify_model(ClipAdapter(model))
        return
    target.parent.mkdir(parents=True,exist_ok=True)
    print('Downloading the public CLIP ViT-B/32 model. No user images or reports are uploaded.',flush=True)
    staging = Path(tempfile.mkdtemp(prefix='clip-prepare-',dir=target.parent))
    try:
        model=SentenceTransformer('sentence-transformers/clip-ViT-B-32',revision=MODEL_REVISION,
                                  device='cpu',trust_remote_code=False)
        verify_model(ClipAdapter(model))
        model.save(str(staging))
        staging.rename(target)
    except Exception:
        # Only a directory created here, never the user's model or record folders.
        shutil.rmtree(staging,ignore_errors=True)
        raise

def prepare_dino():
    from ai_runtime import DINO_FILES, DinoPhotoAdapter
    from huggingface_hub import snapshot_download
    from PIL import Image

    target = ROOT/'models'/'dinov2-small'
    with tempfile.TemporaryDirectory(dir=target.parent) as directory:
        path = Path(directory)
        prepared = all((target/file).is_file() for file in DINO_FILES)
        model = target if prepared else path/'dinov2-small'
        if not prepared:
            print('Downloading DINOv2 Small for photo-to-photo matching...', flush=True)
            snapshot_download('facebook/dinov2-small', revision=DINO_REVISION, local_dir=model,
                              allow_patterns=list(DINO_FILES))
        photo = path/'setup-check.png'
        Image.new('RGB', (32, 32), 'darkgreen').save(photo)
        vector = DinoPhotoAdapter(model).embed_image(photo)
        if not vector or not all(isfinite(value) for value in vector):
            raise RuntimeError('DINOv2 could not produce a valid photo embedding.')
        if not prepared:
            target.mkdir(exist_ok=True)
            for file in DINO_FILES:
                (model/file).replace(target/file)
    print('Local DINOv2 photo matching passed.', flush=True)


def main():
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    os.environ.pop('HF_HUB_OFFLINE', None)
    os.environ.pop('TRANSFORMERS_OFFLINE', None)
    import torch
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    prepare_clip()
    if os.getenv('ENABLE_DINO', '1').casefold() in {'1','true','yes'}:
        try:
            prepare_dino()
        except Exception as error:
            print(f'CLIP is ready. Optional DINOv2 setup failed ({type(error).__name__}). Rerun AI setup to retry.', flush=True)
    print('AI is prepared. Restart Reunite using its START launcher.',flush=True)


if __name__=='__main__':
    main()
