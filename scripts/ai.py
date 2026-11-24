"""Explicit first-time download. Inference itself never uses a remote service."""
import argparse
import json
import os
import sys
import shutil
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
CLIP_REVISION = '327ab6726d33c0e22f920c83f2ff9e4bd38ca37f'
DINO_REVISION = 'f9e44c814b77203eaa57a6bdbbd535f21ede1415'


def _ready(folder, marker):
    return (folder / marker).exists()


def prepare_clip():
    target = ROOT / 'models' / 'clip-ViT-B-32'
    if _ready(target, 'modules.json'):
        print('CLIP already exists. Verifying it offline...', flush=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    print('Downloading the public CLIP ViT-B/32 model. No user images or reports are uploaded.', flush=True)
    from sentence_transformers import SentenceTransformer
    staging = Path(tempfile.mkdtemp(prefix='clip-prepare-', dir=target.parent))
    try:
        model = SentenceTransformer('sentence-transformers/clip-ViT-B-32', revision=CLIP_REVISION,
                                    device='cpu', trust_remote_code=False)
        model.save(str(staging))
        model.encode('a dark green backpack', show_progress_bar=False)
        staging.rename(target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print('CLIP is prepared.', flush=True)


def prepare_dino():
    target = ROOT / 'models' / 'dinov2-base'
    if _ready(target, 'config.json') and (_ready(target, 'model.safetensors') or _ready(target, 'pytorch_model.bin')):
        print('DINOv2 already exists. Verifying it offline...', flush=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    print('Downloading the public DINOv2 ViT-B/14 model for photo matching. No user images are uploaded.', flush=True)
    from transformers import AutoImageProcessor, AutoModel
    staging = Path(tempfile.mkdtemp(prefix='dino-prepare-', dir=target.parent))
    try:
        processor = AutoImageProcessor.from_pretrained('facebook/dinov2-base', revision=DINO_REVISION, use_fast=False)
        model = AutoModel.from_pretrained('facebook/dinov2-base', revision=DINO_REVISION,
                                          trust_remote_code=False)
        processor.save_pretrained(staging)
        model.save_pretrained(staging)
        staging.rename(target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print('DINOv2 is prepared.', flush=True)


def prepare_models():
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    os.environ.pop('HF_HUB_OFFLINE', None)
    os.environ.pop('TRANSFORMERS_OFFLINE', None)
    prepare_clip()
    prepare_dino()
    from lyfind.ai_runtime import LocalAI
    ai = LocalAI()
    if not ai.prepare():
        raise RuntimeError(ai.reason)
    print(ai.reason, flush=True)
    print('AI is prepared. Start LyFind with python3 main.py.', flush=True)




def check_models():
    """Verify matching locally while forbidding network connections."""
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    from lyfind.ai_runtime import LocalAI
    from lyfind.proposal_matching import ProposalMatcher
    from matching import cosine
    from lyfind.seed import sample_image
    from pathlib import Path
    from unittest.mock import patch
    from datetime import date
    import tempfile
    
    photos = ROOT / 'tests' / 'fixtures' / 'photos'
    with tempfile.TemporaryDirectory() as folder:
        p = Path(folder) / 'bag.png'
        p.write_bytes(sample_image())
        with patch('socket.socket.connect', side_effect=RuntimeError('Network is forbidden during inference')):
            engine = LocalAI()
            assert engine.prepare(), engine.reason
            model = ProposalMatcher(engine)
            r = dict(category='bags', description='a dark green backpack', color='green', brand='Campus',
                     place='Library', date_lost=date.today().isoformat())
            i = dict(r, date_found=date.today().isoformat(), photo_path=str(p))
            without = model.evaluate(r, i)
            with_photo = model.evaluate(dict(r, photo_path=str(p)), i)
            assert abs(with_photo['contributions']['photo'] - engine.weights.photo) < .01
            assert with_photo['level'] == 'strong'
            assert with_photo['total'] > 90
            assert without['photo_source'] == 'owner_description'
            proof = {}
            owner, same, other = photos / 'backpack-owner.jpg', photos / 'backpack-same-found.jpg', photos / 'backpack-found.jpg'
            if owner.is_file() and same.is_file() and other.is_file():
                ov = engine.adapter.embed_image(str(owner))
                proof = dict(
                    same_bag=round(cosine(ov, engine.adapter.embed_image(str(same))), 4),
                    different_bag=round(cosine(ov, engine.adapter.embed_image(str(other))), 4),
                )
                lookalike = model.evaluate(
                    dict(r, description='dark backpack with zippers', color='black', photo_path=str(owner)),
                    dict(i, description='dark backpack with zippers', color='black', photo_path=str(other)),
                )
                proof['different_bag_level'] = lookalike['level']
                assert lookalike['level'] != 'strong', lookalike
            print(json.dumps({'runtime': engine.status(), 'fixture_photos': proof,
                              'no_owner_photo': {'photo_source': without['photo_source'], 'total': without['total']},
                              'with_owner_photo': {'total': with_photo['total'], 'method': with_photo['method']}}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Prepare or check LyFind's local AI models")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare', action='store_true', help='Download missing models; requires internet')
    action.add_argument('--check', action='store_true', help='Check models with network access blocked')
    args = parser.parse_args()
    if args.prepare:
        prepare_models()
    else:
        check_models()


if __name__ == '__main__':
    main()
