"""A real local-AI partial match and paraphrased ownership answer.

No arguments: print and verify the trial in a disposable database.
--serve: open the same fictional case for hands-on browser practice on port 8767.
The application's regular database and uploads are never edited.
"""
import argparse
import json
import shutil
import tempfile
from datetime import date
from pathlib import Path

from database import Database
from seed import sample_image
from users import User, hash_password
from web import Application, serve

ROOT=Path(__file__).resolve().parent
ANSWER=("There should be a red membership card in it. I tucked a little blue "
        "receipt behind the cards, probably from Monday. I cannot remember "
        "the wallet's brand, but those two things should still be inside.")
PRIVATE='Blue receipt dated Monday tucked behind a red loyalty card'


def build_trial(root):
    static=root/'static';static.mkdir()
    for name in ('index.html','app.js','style.css'):
        shutil.copyfile(ROOT/'static'/name,static/name)
    index=static/'index.html'
    index.write_text(index.read_text(encoding='utf-8').replace('Reunite | Campus','Reunite Trial | Campus'),encoding='utf-8')
    js=static/'app.js'
    js.write_text(js.read_text(encoding='utf-8').replace('A place for things to find their people.','ISOLATED CLASS TRIAL / fictional records'),encoding='utf-8')
    db=Database(root/'data/trial.sqlite3');db.initialize()
    users={}
    with db.connect() as c:
        for role,name in [('admin','CSA Trial Reviewer'),('student','Trial Student'),('professor','Trial Faculty'),('guest','Alex Trial Guest')]:
            uid=c.execute('INSERT INTO users(name,email,role,password_hash) VALUES(?,?,?,?)',
                          (name,f'demo.{role}@example.test',role,hash_password('DemoOnly!2026') if role=='admin' else '')).lastrowid
            users[role]=User.from_row(c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone())
    app=Application(db,root,True)
    if not app.service.ai.adapter:
        raise RuntimeError('This trial requires actual local AI. Run the AI setup first. '+app.service.ai.reason)
    uploads=root/'data/uploads';filename='fictional-brown-wallet.png'
    (uploads/filename).write_bytes(sample_image('wallet'))
    with db.connect() as c:
        photo=c.execute('INSERT INTO uploads(owner_id,kind,path,mime,original_name) VALUES(?,?,?,?,?)',
                        (users['admin'].id,'item_photo',filename,'image/png','Illustrative trial wallet.png')).lastrowid
    today=date.today().isoformat()
    item=app.service.receive_item(users['admin'],dict(category='wallets',description='Brown leather folding wallet',
              color='Brown',brand='Unbranded',place='Student Center',date_found=today,
              private_details=PRIVATE,photo_id=photo))
    report=app.service.create_lost_report(users['guest'],dict(category='wallets',
              description='Brown wallet lost while visiting campus',color='tan',brand='Unknown',
              place='Campus cafeteria',date_lost=today,identifying_marks='A membership card and a receipt',photo_id=None))
    with db.connect() as c:
        match=dict(c.execute('SELECT * FROM matches WHERE item_id=? AND report_id=?',(item['id'],report['id'])).fetchone())
    assert match['method']=='clip_ai',match
    assert 40<=match['score']<60,match
    return app,users,item,report,match


def demonstrate(app,users,item,report,match):
    print('REUNITE / PARTIAL AI MATCH + FLEXIBLE OWNERSHIP ANSWER')
    print('Fictional case in a separate temporary database. Actual local CLIP inference.\n')
    print('Received item:',item['description'])
    print('Owner description:',report['description'])
    print('Owner photo: none; description-to-photo comparison is used.')
    print('Category: wallets / wallets. Color: Brown / tan.')
    print('Brand: Unbranded / Unknown. Place: Student Center / Campus cafeteria.')
    print(f"\nActual score: {match['score']:.1f} / 100 ({match['level']})")
    details=json.loads(match['score_details'])
    for key,value in details['contributions'].items():
        if value is None:
            print(f"  {key}: unavailable")
            continue
        print(f"  {key}: {value:.4f} / {details['weights'][key]:g}")
    before=app.service.dashboard(users['guest'])
    assert not before['matches']
    print('\nBefore staff confirmation: owner sees no raw suggestion or score.')
    app.service.decide_match(users['admin'],match['id'],True)
    print('CSA reviews the item, confirms the possible match, then invites the owner.')
    assert ANSWER!=PRIVATE and PRIVATE.casefold() not in ANSWER.casefold()
    claim=app.service.submit_claim(users['guest'],dict(item_id=item['id'],report_id=report['id'],
                               answers={'details':ANSWER},consent=True))
    print('\nPrivate CSA record:',PRIVATE)
    print('Owner answer:',ANSWER)
    assert claim['status']=='step1_pending'
    assert not claim['online_verified_by']
    print('After submission: online check pending. No automatic ownership approval.')
    claim=app.service.verify_online(users['admin'],claim['id'],True,
                reason='Trial reviewer: membership/loyalty wording differs, but the red card and blue receipt agree with the hidden contents. Continue with in-person ID and ownership proof.')
    assert claim['status']=='step2_pending'
    assert not claim['in_person_consent'] and not claim['approved_by'] and not claim['released_by']
    print('\nCSA accepts the meaning of the paraphrased answer after reviewing the private details.')
    print('Final stage: in-person check pending; no approval or physical release has occurred.')
    print('PASS: non-perfect Possible match, private results, natural-language answer, staff-controlled decision.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve',action='store_true')
    parser.add_argument('--port',type=int,default=8767)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='reunite-matching-trial-') as directory:
        app,users,item,report,match=build_trial(Path(directory))
        if args.serve:
            print(f"Trial match: {match['score']:.1f}/100 ({match['level']}).",flush=True)
            print('Open CSA admin > Matching. Confirm the suggestion, then sign in as Guest to answer.',flush=True)
            print('Flexible example answer: '+ANSWER,flush=True)
            serve(app,'127.0.0.1',args.port)
        else:
            demonstrate(app,users,item,report,match)


if __name__=='__main__':main()
