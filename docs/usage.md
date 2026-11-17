# Using the library

Start the [Compose installation](installation.md), then open
[http://127.0.0.1:8080](http://127.0.0.1:8080). The library is shared by every
client that can reach the instance. There is no sign-in or per-user storage.

## Configure parsing and translation

In **Settings → PDF parsing**, select a parser and timeout. Surya OCR 2 is the
default for new preferences; Chandra OCR 2 and Infinity-Parser2 Pro/Flash are also
executable choices when the DMR backend supports them. OXR is available with the
managed CUDA plugin. Settings shows model status and resource estimates. See
[Parser setup](deployment/extraction-acceleration.md) before preparing a model.

Saving the selection does not download weights or test inference. **Prepare
parsing model** starts a separate task; the first parse can also prepare missing
weights. Model preparation and inference share the configured resource admission
budgets. Estimates and a prepared status do not certify performance or PDF quality.

In **Settings → Translation service**, choose either:

- Your API service, with its exact protocol, full request URL, model ID, and
  authentication. Responses, compatible Chat Completions, Gemini Interactions,
  and Claude Messages are supported.
- An optional local translator installed through
  [Local translation and analysis](deployment/local-translation.md). Select its
  exact pinned model and supported backend.

Save before starting new work. API keys are stored in backend files and not
returned by the API. A blank key field keeps the existing key unless you explicitly
clear it. Saving does not send a connection test. Testing is a separate confirmed
request and may incur charges.

Choose the default translation language beside the translation model, then use
**Save default translation language**. Built-in models show their documented
target languages; custom API models with unknown coverage keep all languages.
An incompatible saved choice stays visible until you explicitly choose a
supported language. Existing tasks and translated editions keep their language.

In **Settings → Reading preferences**, choose the UI language from the same 20
languages as TwitchDropsMiner. It applies immediately and is saved only in this
browser, independently of translation settings.

Cost controls are off for new configurations. Enable them if you want configured
pricing and a per-document budget enforced. Unknown charges remain unpriced;
turning controls off does not make a service free. Existing tasks retain the
service, credential revision, and model selection recorded when they were created.

## Upload and process a PDF

1. Open **Upload PDF** and select files. Defaults are 50 MiB and 200 pages per PDF,
   with up to ten PDFs in a batch. Only PDF input is accepted.
2. Choose source-only processing or parsing and translation. Source-only processing
   creates an original-language reading version without authorizing translation.
3. For translation, choose the target language and preparation mode, inspect the
   displayed service, and set a budget when cost controls require it.
4. Submit the batch. Choosing translation and submitting authorizes the necessary
   text, context, and terminology to be sent to the displayed saved service.
   The task cannot silently switch to a different provider or model.
5. Follow the task's stages and result. If translation settings or a required
   budget are incomplete, local parsing can finish first; complete the missing
   configuration and start translation from the document later.

Metadata lookup may query Crossref with a discovered DOI or a conservative
title/author query. It runs separately from translation. Missing or uncertain
matches keep the filename, and lookup does not overwrite your edited title.

New UI operations publish their completed reading result automatically. Content
warnings do not require human approval; execution failures, missing authorization,
and version conflicts still need their own recovery action.

## Choose preparation and terminology

**Pre-translation preparation** controls the context supplied with translation:

- **Extractive preparation**, the default, collects source excerpts, headings,
  definitions, and term candidates without another model call.
- **Current API model** adds one bounded analysis request to the saved provider.
- **Separate local model** uses the independently configured MiniCPM5-1B analyst
  before translating through the selected API or local translator.
- **No paper-level preparation** keeps the legacy request flow.

Preparation is bounded and does not mean a model read the full paper. Its wording
and terminology are suggestions, with source evidence and coverage limits visible
in the editor. Explicit glossary entries take precedence. Local analysis followed
by API translation still sends the selected context to that API.

## Read, organize, and edit

Use the library to search, tag, star, and archive documents. Open a document to
read the original PDF, inspect processing records, start translation from saved
source, or manage its reading versions. Source-only content is not labeled as a
completed translation.

The bilingual reader keeps the original content for comparison. Its theme, font,
code-font, and line-height controls do not retranslate the paper. Management UI
language and translation language are independent. Reader controls use the saved
translation locale where a catalog exists and otherwise use English.

Open the translation editor to change a passage, request a candidate, inspect
preparation evidence, or review quality findings. Human review is optional. A
candidate does not replace the current passage until you accept it. Save edited
text before confirming a passage as reviewed or explicitly saving it to translation
memory; the application does not invent human confirmation.

Use source correction when PDF evidence supports an extraction repair. Corrections
create a new source revision. Authors, affiliations, identifiers, and references
remain original-only when explicit metadata evidence supports that classification;
ambiguous body prose remains translatable.

Concurrent tabs can encounter a version conflict. Reload the latest version and
compare your changes before saving again. Do not keep resubmitting stale edits.

## Reading versions and offline export

Sealed source and translation revisions and published files are immutable.
Publishing verifies the complete artifact before switching the current reading
pointer. You can retain earlier versions, switch the current publication, or
preview a newer reader template from saved translation without calling the model
again. Creating a preview does not itself select that publication.

Export the selected publication as self-contained HTML or a resource bundle.
Offline exports omit instance-navigation links and embed their reading resources.
An explicit draft export preserves untranslated passages as original content and
does not publish the draft. Downloaded copies are outside the instance: deleting a
document later does not recall them.

Quality findings, missing translations, and absent human review do not block
sealing, publication, or export. They remain visible as findings or original-content
fallbacks. Check important passages, formulas, numbers, and tables against the PDF.

## Task recovery and maintenance

Tasks retain stages, actual model identities, timings, attempts, and redacted logs.
Pausing prevents new requests; it cannot revoke one already sent. An unknown
network outcome is kept for explicit recovery and is not automatically resent.
Clearing finished task history hides its entries without deleting immutable data.

Use [Troubleshooting](troubleshooting.md) for common failures. Use the maintenance
service for [backups and restore](ops/restore.md) and
[storage retention](ops/retention.md). Maintenance may deliberately leave writes
or dispatch paused until you inspect the result and reopen them.
