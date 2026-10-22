"""Make `import omni.physxdemos` work again on Isaac Sim 5.1.0.

Env_Config/Garment/Particle_Garment.py and Env_Config/Human/Human.py both do
`import omni.physxdemos as demo` at module scope. On Isaac Sim 4.5.0 that
module happened to be importable out of the box; on 5.1.0 the extension that
provides it (`omni.physx.demos`) is present in the registry but not enabled by
the default app config, so the bare import raises ModuleNotFoundError before
either file's class body is even reached.

Neither file ever actually USES the module -- `demo.` appears nowhere in the
repo -- so this is a dead import, but it still has to resolve.

Rather than editing the user's source (the point of this container is to leave
the host repo untouched), a meta-path finder is installed here that enables the
Kit extension the first time anything asks for `omni.physxdemos`, then hands the
import back to the normal machinery. It has to be lazy like this because the
extension manager does not exist until SimulationApp has been constructed,
which happens long after interpreter startup.
"""
import importlib.machinery
import importlib.util
import sys


class _PhysxDemosFinder:
    """Enable omni.physx.demos on first request for omni.physxdemos."""

    TARGET = "omni.physxdemos"
    EXTENSION = "omni.physx.demos"

    def __init__(self):
        self._tried = False

    def find_spec(self, fullname, path=None, target=None):
        # Only ever act once: after enabling, the real PathFinder ahead of us in
        # sys.meta_path resolves the module, and re-entering here (find_spec
        # below walks sys.meta_path again) would recurse.
        if fullname != self.TARGET or self._tried:
            return None
        self._tried = True

        try:
            import omni.kit.app

            app = omni.kit.app.get_app()
            if app is None:
                return None
            mgr = app.get_extension_manager()
            mgr.set_extension_enabled_immediate(self.EXTENSION, True)
        except Exception:  # noqa: BLE001
            # No Kit app yet, or the extension is gone in this version. Fall
            # through to a stub rather than taking the whole env down over an
            # import the repo never uses.
            return self._stub_spec(fullname)

        # Enabling put the extension's own directory on sys.path; `omni` is a
        # namespace package so its __path__ picks that up automatically.
        import omni

        spec = importlib.machinery.PathFinder.find_spec(fullname, list(omni.__path__))
        return spec if spec is not None else self._stub_spec(fullname)

    @staticmethod
    def _stub_spec(fullname):
        loader = importlib.machinery.SourceFileLoader(fullname, __file__)
        spec = importlib.util.spec_from_loader(fullname, loader=None)
        spec.loader = _StubLoader()
        return spec


class _StubLoader:
    def create_module(self, spec):
        import types

        mod = types.ModuleType(spec.name)
        mod.__doc__ = ("Stub standing in for omni.physxdemos, which this Isaac Sim "
                       "build does not provide. The importing code never calls into it.")
        return mod

    def exec_module(self, module):
        return None


if not any(isinstance(f, _PhysxDemosFinder) for f in sys.meta_path):
    sys.meta_path.append(_PhysxDemosFinder())


# --- Optional WebRTC livestream: ./run.sh gui --stream / replay --stream -----
#
# Headless servers (e.g. a Google Cloud VM) have no X display, so the GUI
# session is streamed instead. Done here rather than in the env scripts so the
# competition sources -- whose SHA-256s are written into every recording and
# evaluation -- stay byte-identical. Inactive unless STRETCH4_LIVESTREAM=1.
#
# Mirrors Isaac Sim 6.0.1 itself:
#   * standalone_examples/api/isaacsim.simulation_app/livestream.py:
#     headless=True + hide_ui=False, drawMouse, then enable
#     omni.kit.livestream.app once the app exists;
#   * tools/docker/data/runheadless.sh: ISAACSIM_HOST / ISAACSIM_SIGNAL_PORT /
#     ISAACSIM_STREAM_PORT -> /exts/omni.kit.livestream.app/primaryStream/
#     publicIp / signalPort / streamPort;
#   * apps/isaacsim.exp.full.streaming.kit: streamType webrtc, allowResize.
#
# The scripts do `from isaacsim import SimulationApp`, and importing `isaacsim`
# bootstraps the Kit kernel, so it must not be imported here eagerly. Instead
# the first import of `isaacsim` is intercepted, completed normally, and only
# then is SimulationApp.__init__ wrapped.
import os

_LIVESTREAM_EXTENSION = "omni.kit.livestream.app"
_LIVESTREAM_SETTINGS = "/exts/omni.kit.livestream.app/primaryStream"


def _livestream_launch_config(config):
    config = dict(config or {}, headless=True, hide_ui=False)
    args = list(config.get("extra_args") or [])
    args.append(f"--{_LIVESTREAM_SETTINGS}/streamType=webrtc")
    for env, key in (("ISAACSIM_HOST", "publicIp"),
                     ("ISAACSIM_SIGNAL_PORT", "signalPort"),
                     ("ISAACSIM_STREAM_PORT", "streamPort")):
        value = os.environ.get(env, "").strip()
        if value:
            args.append(f"--{_LIVESTREAM_SETTINGS}/{key}={value}")
    args += [
        "--/app/livestream/allowResize=true",
        "--/app/window/drawMouse=true",
        # A client disconnect must not end the teleop session (the streaming
        # .kit sets this true for its own one-shot sessions).
        "--/exts/omni.services.livestream.session/quitOnSessionEnded=false",
    ]
    config["extra_args"] = args
    return config


def _livestream_start(app):
    import omni.kit.app

    manager = omni.kit.app.get_app().get_extension_manager()
    if not manager.set_extension_enabled_immediate(_LIVESTREAM_EXTENSION, True):
        raise RuntimeError(f"Could not enable {_LIVESTREAM_EXTENSION}: livestream unavailable in this image")
    app.update()
    print(f"[livestream] {_LIVESTREAM_EXTENSION} enabled: host={os.environ.get('ISAACSIM_HOST', '?')} "
          f"signal={os.environ.get('ISAACSIM_SIGNAL_PORT', '49100')}/tcp "
          f"media={os.environ.get('ISAACSIM_STREAM_PORT', '47998')}/udp", flush=True)


def _patch_simulation_app(module):
    cls = getattr(module, "SimulationApp", None)
    if cls is None or getattr(cls, "_phyrc_livestream", False):
        return
    original_init = cls.__init__

    def __init__(self, launch_config=None, *args, **kwargs):
        original_init(self, _livestream_launch_config(launch_config), *args, **kwargs)
        _livestream_start(self)

    cls.__init__ = __init__
    cls._phyrc_livestream = True


class _LivestreamFinder:
    """Wrap SimulationApp right after the real `isaacsim` package has loaded."""

    def __init__(self):
        self._tried = False

    def find_spec(self, fullname, path=None, target=None):
        if fullname != "isaacsim" or self._tried:
            return None
        self._tried = True
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None or not hasattr(spec.loader, "exec_module"):
            return None
        original_exec = spec.loader.exec_module

        def exec_module(module):
            original_exec(module)
            _patch_simulation_app(module)

        spec.loader.exec_module = exec_module
        return spec


if os.environ.get("STRETCH4_LIVESTREAM") == "1" and not any(
        isinstance(f, _LivestreamFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _LivestreamFinder())
