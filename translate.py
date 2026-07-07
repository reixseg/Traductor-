"""Traducción automática hacia español con caché y lotes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from deep_translator import GoogleTranslator

from config import CONFIG
from utils import detect_language, needs_translation, normalize_text


class TextTranslator:
    def __init__(self) -> None:
        self._translator = GoogleTranslator(source="auto", target=CONFIG.target_lang)
        self._cache: dict[str, str] = {}
        self._lang_cache: dict[str, str] = {}
        self._pool = ThreadPoolExecutor(max_workers=4)

    def translate_many(self, texts: list[str]) -> dict[str, str]:
        results: dict[str, str] = {}
        pending: list[tuple[str, str]] = []

        for text in texts:
            cleaned = normalize_text(text)
            if not needs_translation(cleaned):
                continue

            cached = self._cache.get(cleaned)
            if cached is not None:
                results[text] = cached
                continue

            pending.append((text, cleaned))

        if not pending:
            return results

        batch_size = CONFIG.translate_batch_size
        for start in range(0, len(pending), batch_size):
            chunk = pending[start : start + batch_size]
            chunk_results = self._translate_chunk(chunk)
            results.update(chunk_results)

        return results

    def _translate_chunk(self, chunk: list[tuple[str, str]]) -> dict[str, str]:
        out: dict[str, str] = {}
        originals = [orig for orig, _ in chunk]
        cleaned_list = [clean for _, clean in chunk]

        try:
            translated_list = self._translator.translate_batch(cleaned_list)
            for (orig, cleaned), translated in zip(chunk, translated_list):
                if translated and str(translated).strip():
                    tr = str(translated).strip()
                    out[orig] = tr
                    self._cache[cleaned] = tr
                    lang, _ = detect_language(cleaned)
                    self._lang_cache[cleaned] = lang
        except Exception:
            futures = {
                self._pool.submit(self._translate_one, orig, cleaned): orig
                for orig, cleaned in chunk
            }
            for future in as_completed(futures):
                orig = futures[future]
                try:
                    tr = future.result()
                    if tr:
                        out[orig] = tr
                except Exception:
                    pass

        self._trim_cache()
        return out

    def _translate_one(self, original: str, cleaned: str) -> str | None:
        cached = self._cache.get(cleaned)
        if cached is not None:
            return cached
        try:
            translated = self._translator.translate(cleaned)
        except Exception:
            return None
        if not translated or not str(translated).strip():
            return None
        tr = str(translated).strip()
        self._cache[cleaned] = tr
        lang, _ = detect_language(cleaned)
        self._lang_cache[cleaned] = lang
        return tr

    def _trim_cache(self) -> None:
        if len(self._cache) > 800:
            for key in list(self._cache.keys())[:400]:
                self._cache.pop(key, None)
                self._lang_cache.pop(key, None)

    def clear_cache(self) -> None:
        self._cache.clear()
        self._lang_cache.clear()

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
