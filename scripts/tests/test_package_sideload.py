"""Packaging checks use a synthetic .app fixture, not an installable iOS app."""
import importlib.machinery
import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "package-sideload"


class SideloadPackagingTests(unittest.TestCase):
    def load_packager(self):
        self.assertTrue(SCRIPT.is_file(), "Sideload packager is missing")
        loader = importlib.machinery.SourceFileLoader("sideload_packager", str(SCRIPT))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module

    def test_main_app_only_retains_executable_resources_and_source(self):
        packager = self.load_packager()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / "Fixture.app"
            app.mkdir()
            info = {"CFBundleIdentifier": "com.example.fixture", "CFBundleExecutable": "Fixture",
                    "CFBundleSupportedPlatforms": ["iPhoneOS"], "NSSupportsLiveActivities": True,
                    "NSSupportsLiveActivitiesFrequentUpdates": True}
            (app / "Info.plist").write_bytes(plistlib.dumps(info))
            (app / "Fixture").write_bytes(b"fixture executable bytes")
            (app / "Fixture").chmod(0o755)
            (app / "Assets.car").write_bytes(b"fixture assets")
            plugins = app / "PlugIns"
            (plugins / "Share.appex").mkdir(parents=True)
            (plugins / "Share.appex/Info.plist").write_bytes(b"fixture extension")
            output = root / "fixture.ipa"
            packager.package_app(app, output)
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                self.assertFalse(any("PlugIns/" in name for name in archive.namelist()))
                self.assertEqual(archive.read("Payload/Fixture.app/Fixture"), b"fixture executable bytes")
                self.assertEqual(archive.read("Payload/Fixture.app/Assets.car"), b"fixture assets")
                packaged = plistlib.loads(archive.read("Payload/Fixture.app/Info.plist"))
                self.assertFalse(packaged["NSSupportsLiveActivities"])
                self.assertFalse(packaged["NSSupportsLiveActivitiesFrequentUpdates"])
                self.assertEqual(packaged["HermesKeychainAccessGroup"], "")
                self.assertEqual(packaged["HermesAPSEnvironment"], "disabled")
                mode = archive.getinfo("Payload/Fixture.app/Fixture").external_attr >> 16
                self.assertEqual(mode & 0o111, 0o111)
            self.assertTrue((app / "PlugIns/Share.appex").exists(), "Never change the build product")
            self.assertTrue(plistlib.loads((app / "Info.plist").read_bytes())["NSSupportsLiveActivities"])

    def test_simulator_build_is_not_mislabelled_as_device_ipa(self):
        packager = self.load_packager()
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "Simulator.app"
            app.mkdir()
            (app / "Info.plist").write_bytes(plistlib.dumps({"CFBundleSupportedPlatforms": ["iPhoneSimulator"]}))
            with self.assertRaises(ValueError):
                packager.package_app(app, Path(directory) / "bad.ipa")


if __name__ == "__main__":
    unittest.main()
