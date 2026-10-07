"""Traducción offline con Argos Translate.

- No usa Google ni ningún servicio en línea para traducir.
- Solo necesita internet la primera vez, para descargar los paquetes de idioma.
"""

from __future__ import annotations

from config import CONFIG
from logger import LOGGER
from utils import detect_language, needs_translation, normalize_text

# Códigos de langdetect que difieren de los de Argos.
_LANG_ALIASES = {"zh-cn": "zh", "zh-tw": "zt"}


class TextTranslator:
    def __init__(self) -> None:
        import argostranslate.package as argos_package
        import argostranslate.translate as argos_translate

        self._package = argos_package
        self._argos = argos_translate

        self._target = CONFIG.target_lang
        self._sources = self._configured_sources()
        self._default_source = self._sources[0]

        self._cache: dict[str, str] = {}  # "" = no hace falta mostrar traducción
        self._translations: dict[str, object] = {}
        self._unavailable: set[str] = set()
        self._last_logged_error: str | None = None
        self.last_error: str | None = None

        # Instala (si falta) y carga los idiomas configurados.
        for code in self._sources:
            if self._get_translation(code, allow_install=True) is None:
                LOGGER.warning(
                    "Idioma Argos no disponible: %s -> %s (revisa internet en la primera ejecución)",
                    code,
                    self._target,
                )

    # ------------------------------------------------------------------
    # Idiomas y paquetes
    # ------------------------------------------------------------------
    @staticmethod
    def _configured_sources() -> list[str]:
        if CONFIG.source_lang and CONFIG.source_lang != "auto":
            return [CONFIG.source_lang.strip().lower()]
        codes = [c.strip().lower() for c in CONFIG.argos_source_languages if c and c.strip()]
        return codes or ["en"]

    def _find_installed(self, code: str):
        get_langs = self._argos.get_installed_languages
        if hasattr(get_langs, "cache_clear"):
            get_langs.cache_clear()
        langs = get_langs()
        src = next((l for l in langs if l.code == code), None)
        dst = next((l for l in langs if l.code == self._target), None)
        if src is None or dst is None:
            return None
        return src.get_translation(dst)

    @staticmethod
    def _find_package(available, from_code: str, to_code: str):
        return next(
            (p for p in available if p.from_code == from_code and p.to_code == to_code),
            None,
        )

    def _install_language(self, code: str) -> bool:
        try:
            LOGGER.info("Descargando paquete de idioma Argos: %s -> %s", code, self._target)
            self._package.update_package_index()
            available = self._package.get_available_packages()

            pairs = [(code, self._target)]
            if self._find_package(available, code, self._target) is None:
                # Sin paquete directo: se usa inglés como puente.
                pairs = [(code, "en"), ("en", self._target)]

            for src, dst in pairs:
                pkg = self._find_package(available, src, dst)
                if pkg is None:
                    LOGGER.warning("No existe un paquete Argos %s -> %s", src, dst)
                    return False
                self._package.install_from_path(pkg.download())
            return True
        except Exception as exc:
            self._report_error(exc)
            return False

    def _get_translation(self, code: str, allow_install: bool):
        if code in self._translations:
            return self._translations[code]
        if code in self._unavailable and not allow_install:
            return None

        translation = self._find_installed(code)
        if translation is None and allow_install and CONFIG.argos_auto_install:
            if self._install_language(code):
                translation = self._find_installed(code)

        if translation is None:
            self._unavailable.add(code)
            return None

        self._unavailable.discard(code)
        self._translations[code] = translation
        return translation

    def _pick_source(self, cleaned: str) -> str:
        if CONFIG.source_lang and CONFIG.source_lang != "auto":
            return self._default_source
        lang, prob = detect_language(cleaned)
        lang = _LANG_ALIASES.get(lang, lang)
        if prob >= 0.8 and lang in self._sources:
            return lang
        return self._default_source

    # ------------------------------------------------------------------
    # Traducción
    # ------------------------------------------------------------------
    def _report_error(self, exc: Exception) -> None:
        message = f"{type(exc).__name__}: {exc}"
        self.last_error = message
        if message != self._last_logged_error:
            LOGGER.warning("Error de traducción: %s", message)
            self._last_logged_error = message

    def _translate_text(self, cleaned: str) -> str | None:
        code = self._pick_source(cleaned)
        translation = self._get_translation(code, allow_install=False)
        if translation is None and code != self._default_source:
            translation = self._get_translation(self._default_source, allow_install=False)
        if translation is None:
            raise RuntimeError(f"Idioma no disponible: {code} -> {self._target}")

        result = str(translation.translate(cleaned)).strip()
        return result or None

    def warmup(self) -> None:
        """Carga el modelo antes del primer ciclo para que no sea lento."""
        try:
            self._translate_text("Hello world.")
        except Exception as exc:
            self._report_error(exc)

    def translate_many(self, texts: list[str]) -> dict[str, str]:
        self.last_error = None
        results: dict[str, str] = {}

        for text in texts:
            cleaned = normalize_text(text)
            if not needs_translation(cleaned):
                continue

            cached = self._cache.get(cleaned)
            if cached is not None:
                if cached:
                    results[text] = cached
                continue

            try:
                translated = self._translate_text(cleaned)
            except Exception as exc:
                self._report_error(exc)
                continue

            if not translated or translated.casefold() == cleaned.casefold():
                self._cache[cleaned] = ""  # nombre propio o texto igual: no tapar nada
                continue

            self._cache[cleaned] = translated
            results[text] = translated

        self._trim_cache()
        return results

    def translate_if_english(self, text: str) -> str | None:
        cleaned = normalize_text(text)
        if not needs_translation(cleaned):
            return None
        try:
            return self._translate_text(cleaned)
        except Exception as exc:
            self._report_error(exc)
            return None

    def _trim_cache(self) -> None:
        if len(self._cache) > 800:
            for key in list(self._cache.keys())[:400]:
                self._cache.pop(key, None)

    def clear_cache(self) -> None:
        self._cache.clear()

    def shutdown(self) -> None:
        pass
