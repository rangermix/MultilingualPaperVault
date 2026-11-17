# Third-party notices

Original Paper Translation code is Copyright (c) 2026 Fengqing Liu and licensed
under the root [GNU Affero General Public License, version 3 only](LICENSE)
(`AGPL-3.0-only`).
The following material retains its own terms; the project license does not replace
them. These notices accompany the application image at `/app/THIRD_PARTY_NOTICES.md`.

| Material | Terms and retained evidence |
| --- | --- |
| Chandra layout prompt in `src/packages/parsers/page_prompts.py` | Apache-2.0, Copyright 2025 Endless Labs, Inc.; [full upstream license](res/vendor/chandra-prompts/LICENSE) and [pinned provenance](res/vendor/chandra-prompts/provenance.json). The upstream f-strings were expanded and whitespace normalized; no Chandra SDK is bundled. |
| KaTeX JavaScript runtime | Reader-v18 uses 0.19.1 with its [MIT license](res/vendor/katex-0.19.1/LICENSE) and [pinned package provenance](res/vendor/katex-0.19.1/provenance.json). Historical readers retain 0.18.7 with its [MIT license](res/vendor/katex-0.18.7/LICENSE) and [pinned package provenance](res/vendor/katex-0.18.7/provenance.json). |
| Adobe Source Han Sans 2.005R (思源黑体) | [SIL Open Font License 1.1](res/vendor/reader-fonts/SourceHanSans-OFL.txt). The unmodified Simplified Chinese regional variable WOFF2 is the default reader body font. [Font provenance and hashes](res/vendor/reader-fonts/provenance.json) |
| JetBrains Mono 2.304 | [SIL Open Font License 1.1](res/vendor/reader-fonts/JetBrainsMono-OFL.txt). Four unmodified reader code-font variants. [Font provenance and hashes](res/vendor/reader-fonts/provenance.json) |
| Two original arXiv PDFs | [Attribution notice](res/reference/legacy-NOTICE.md), [CC BY 4.0 license](res/reference/CC-BY-4.0.txt) and [exact PDF provenance](res/reference/legacy-provenance.json). The source snapshot omits the optional bilingual HTML and extracted figure files. |

Python, JavaScript, native packages and base images retain their respective
licenses. Their dependency closures are locked in `uv.lock` and
`src/apps/web/package-lock.json`; installed Python/system inventories are generated
in `/app/release/` during the image build. An inventory is not a replacement for
the notices supplied with those dependencies or an approval of every license.
The built management UI includes the bundled JavaScript dependency notices at
`/frontend-licenses.txt`.
The database image retains its base-image notices and includes the project's
AGPL-3.0-only license for its custom build recipe at
`/usr/local/share/library-release/PROJECT-LICENSE`.

Parser and optional translation model weights are downloaded separately on explicit
preparation/use. Their pinned manifests record their own licenses, including
OpenRAIL, Apache, Gemma and custom terms; they are not relicensed under AGPLv3 and are
not bundled into the application image.

TranslateGemma's native prompt and language-name mapping follow the
[Google model format](https://huggingface.co/google/translategemma-4b-it) and its
[Gemma terms](https://ai.google.dev/gemma/terms). Public GGUF/MLX conversions retain
those model terms. PLaMo 3's separately downloaded bundles and custom tokenizer
modules retain the
[PLaMo Community License](https://plamo.preferredai.jp/info/plamo-community-license-en);
the pinned English license is included in those model artifacts. These model
terms are independent of the project's code license.

Paper, font, and model attribution identifies the respective upstream authors.
Previously installed publications keep their stored resources, licenses and
provenance for reading and exports.
