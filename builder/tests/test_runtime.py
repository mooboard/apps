"""Custom source packages join the signed catalog without becoming renderer presets."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import build

class RuntimePackages(unittest.TestCase):
    def setUp(self):
        self.work=tempfile.TemporaryDirectory();self.addCleanup(self.work.cleanup)
        self.root=Path(self.work.name);self.folder=self.root/'Tools'/'Custom Tool';self.folder.mkdir(parents=True)
        self.manifest={'format':3,'id':'custom-tool','name':'Custom Tool','version':'1.0.0','by':'Developer','description':'A generic custom tool.','category':'Tools','runtime':'lua54','minFirmware':'0.4.1','boards':['s3','p4'],'settings':[],'controls':[],'sources':[]}
        (self.folder/'app.lua').write_text('return {frame=function() screen.pixel(1,1,0xffffff) end}\n')
    def load(self):
        (self.folder/'mooboard.json').write_text(json.dumps(self.manifest))
        return build.load_app(self.root,'Tools','Custom Tool')
    def test_repeatable_source_container_and_catalog_row(self):
        row,icon,body,boards,kind,extra=self.load()
        self.assertEqual(body,self.load()[2]);self.assertEqual('lua54',row['uses']);self.assertEqual(3,kind)
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            self.assertEqual(['mooboard.json','app.lua','icon.png'],archive.namelist())
            self.assertTrue(all(entry.compress_type==zipfile.ZIP_STORED for entry in archive.infolist()))
    def test_current_store_categories_include_clock_faces_and_ai(self):
        self.assertEqual(('Lifestyle','Ambiance','Clock Faces','Games','Tools','AI'),build.CATEGORIES)
    def test_undeclared_credential_files_and_wrong_categories_are_refused(self):
        (self.folder/'credentials.json').write_text('{}')
        with self.assertRaises(build.Refused):self.load()
        (self.folder/'credentials.json').unlink();self.manifest['category']='Games'
        with self.assertRaises(build.Refused):self.load()
    def test_binary_source_and_literal_api_headers_are_refused(self):
        (self.folder/'app.lua').write_bytes(b'\x1bLua')
        with self.assertRaises(build.Refused):self.load()
        (self.folder/'app.lua').write_text('return {frame=function() end}')
        self.manifest['sources']=[{'key':'feed','url':'https://example.com/data','refresh':60,'headers':{'Authorization':'Bearer hardcoded-value'}}]
        with self.assertRaises(build.Refused):self.load()

if __name__=='__main__':unittest.main()
