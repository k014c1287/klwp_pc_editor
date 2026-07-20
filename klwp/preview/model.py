"""Editor-facing facade for preview state, formulas and animation."""

from ..formula import _as_number
from .animation import AnimationTransform, LoopProgress
from .globals import (
    ModuleValueResolver,
    PreviewDateValues,
    RootGlobalValues,
    merge_local_globals,
)
from .pages import PreviewPageCounter, ScrollFadeRuleDetector
from .state import PreviewStateResetter, preview_boolean


class PreviewModelMixin:
    def _doc_size(self):
        document_width, document_height = self.memory['device_res']
        height = round(720.0 * document_height / document_width)
        return 720.0, height

    @staticmethod
    def _preview_bool(value):
        return preview_boolean(value)

    def _preview_page_count(self):
        archive = self.memory['archive']
        counter = PreviewPageCounter(archive.root_module())
        return counter.count()

    def _reset_preview_state(self):
        PreviewStateResetter(self).reset()

    def _update_preview_page_label(self):
        memory = self.memory
        label = memory.optional("preview_page_label")
        if label is None:
            return
        page = self.memory['preview_scroll'] + 1
        label.configure(text=f"{page:.2f} / {self._preview_page_count()}")

    def _scroll_fade_triplet(self):
        archive = self.memory['archive']
        detector = ScrollFadeRuleDetector(archive.modules())
        return detector.has_triplet()

    @staticmethod
    def _animation_center(animation, default=0.0):
        return AnimationTransform.center(animation, default)

    def _loop_progress(self, animation):
        memory = self.memory
        started_at = memory.optional("_loop_started_at")
        return LoopProgress(started_at).for_animation(animation)

    def _animation_transform(self, item):
        return AnimationTransform(self, item).calculate()

    def _root_globals(self):
        return RootGlobalValues(self).values()

    def _preview_df(self):
        memory = self.memory
        timestamp = memory.optional("preview_ts")
        if timestamp is not None:
            return PreviewDateValues(timestamp).values()
        archive = self.memory['archive']
        information = archive["preset"].get("preset_info", {})
        return PreviewDateValues(information.get("ts")).values()

    @staticmethod
    def _with_local_globals(item, global_values):
        return merge_local_globals(item, global_values)

    def _value(self, item, key, default=None, globals_=None):
        global_values = globals_ or self._root_globals()
        resolver = ModuleValueResolver(self, global_values)
        return resolver.resolve(item, key, default)

    def _number(self, item, key, default=0.0, globals_=None):
        value = self._value(item, key, default, globals_)
        return _as_number(value, default)
