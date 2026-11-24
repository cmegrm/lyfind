"""Exercise the real launch/reopen/stop lifecycle without opening a browser."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from desktop_launcher import start,stop,health,read_state,instance_id
from mac_bootstrap import install


class DesktopLaunchTests(unittest.TestCase):
    def test_real_server_starts_reopens_without_duplicate_and_stops(self):
        with tempfile.TemporaryDirectory(prefix='reunite-launch-test-') as folder:
            root=Path(folder)
            source=Path(__file__).resolve().parents[1]
            for file in source.glob('*.py'):shutil.copyfile(file,root/file.name)
            shutil.copyfile(source/'schema.sql',root/'schema.sql')
            shutil.copytree(source/'lyfind',root/'lyfind')
            try:
                with patch.dict(os.environ,{'ENABLE_AI':'0','DEMO_MODE':'1'}), patch('desktop_launcher.open_url') as open_url:
                    url=start(root,timeout=30)
                    state=read_state(root);pid=state['pid']
                    self.assertEqual(health(state['port'])['instance'],instance_id(root))
                    self.assertEqual(health(state['port'])['launch_id'],state['launch_id'])
                    self.assertEqual(health(state['port'])['mode'],'live')
                    self.assertTrue(health(state['port'])['setup_required'])
                    open_url.assert_called_once_with(url+'#setup='+state['setup_key'])
                    self.assertEqual(start(root,browser=False,timeout=30),url)
                    self.assertEqual(read_state(root)['pid'],pid)
                    testing=start(root,demo=True,timeout=30)
                    self.assertNotEqual(testing,url)
                    open_url.assert_called_with(testing)
                    test_state=read_state(root,demo=True)
                    self.assertEqual(health(test_state['port'])['mode'],'test')
                    self.assertNotIn('setup_key',test_state)
                    self.assertTrue((root/'data/demo.sqlite3').exists())
                    self.assertTrue((root/'data/csa.sqlite3').exists())
                    self.assertTrue(any((root/'data/test-uploads').glob('sample-*.png')))
                    self.assertFalse(any((root/'data/uploads').glob('sample-*.png')))
                    self.assertTrue(stop(root,demo=True));self.assertFalse(health(test_state['port']))
                    self.assertTrue(health(state['port']))
                    self.assertTrue(stop(root));self.assertFalse(health(state['port']))
            finally:
                stop(root,demo=True)
                stop(root)

    def test_wrapped_python_uses_listening_server_pid_and_matches_launch_id(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            wrapper = Mock(pid=1234)
            wrapper.poll.return_value = None
            with (patch('desktop_launcher.subprocess.Popen', return_value=wrapper) as popen,
                  patch('desktop_launcher.choose_port', return_value=8766),
                  patch('desktop_launcher.time.sleep'),
                  patch('desktop_launcher.health') as health_check):
                server = {'application': 'reunite', 'instance': instance_id(root),
                          'mode': 'live', 'pid': 5678, 'setup_required': True}

                def probe(port):
                    if port == 8765:
                        return {}
                    if health_check.call_count == 2:
                        return dict(server, launch_id='another-launch')
                    return dict(server, launch_id=popen.call_args.kwargs['env']['REUNITE_DESKTOP_LAUNCH_ID'])

                health_check.side_effect = probe
                self.assertEqual(start(root, browser=False), 'http://127.0.0.1:8766/')
                state = read_state(root)
                self.assertEqual(state['pid'], 5678)
                self.assertEqual(health_check.call_count, 3)
                self.assertIn('setup_key', state)
                with patch('desktop_launcher.os.kill') as kill:
                    health_check.side_effect = None
                    health_check.return_value = dict(server, launch_id='another-launch')
                    self.assertFalse(stop(root))
                    kill.assert_not_called()
                    health_check.side_effect = [dict(server, launch_id=state['launch_id']), {}]
                    self.assertTrue(stop(root))
                    self.assertEqual(kill.call_args.args[0], 5678)

    def test_stop_does_not_kill_a_different_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data').mkdir()
            (root/'data/desktop-server.json').write_text('{"port":8765,"pid":1}')
            with patch('desktop_launcher.health',return_value={'application':'reunite','instance':'another-copy','pid':1}),patch('desktop_launcher.os.kill') as kill:
                self.assertFalse(stop(root));kill.assert_not_called()

    def test_mac_bootstrap_updates_code_without_overwriting_saved_state(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);source=base/'bundle';home=base/'user-library';runtime=base/'python'
            source.mkdir();home.mkdir();(runtime/'bin').mkdir(parents=True)
            (runtime/'bin/python3.12').write_text('runtime fixture')
            (source/'main.py').write_text('new code')
            for name in ['data/record.txt','models/weight.txt','.env','.venv/fixture.txt']:
                a=source/name;a.parent.mkdir(parents=True,exist_ok=True);a.write_text('bundled value must not replace user value')
                b=home/name;b.parent.mkdir(parents=True,exist_ok=True);b.write_text('existing user value')
            install(source,runtime,home)
            self.assertEqual((home/'main.py').read_text(),'new code')
            for name in ['data/record.txt','models/weight.txt','.env','.venv/fixture.txt']:
                self.assertEqual((home/name).read_text(),'existing user value')


if __name__=='__main__':unittest.main()
