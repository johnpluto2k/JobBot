# LaTeX: Overleaf and local builds

Résumés and letters are LaTeX. The source of truth for each file is the copy
on disk (`resume/master_resume.tex`, `applications/<Company>_<Role>/source/*.tex`).
Overleaf is where the owner sees and compiles them. Keep the two in step:
whenever one changes, update the other in the same session.

There are three ways to get a PDF. Use the first that is available.

## 1. Local build (fastest, optional)

If `pdflatex` (MiKTeX, MacTeX, TeX Live) or `tectonic` is installed:

```
cd applications/<Company>_<Role>/source
pdflatex -interaction=nonstopmode resume.tex
```

Copy the PDF one level up under the upload name, delete `.aux`, `.log` and
`.out`, then run the checker and look at the page. On Windows a PDF that is
open in a viewer can't be overwritten; if the copy fails, ask the owner to
close it.

A local TeX install is not required. Don't ask the owner to install one.

## 2. Overleaf through the browser

Needs Claude in Chrome and the owner signed in to Overleaf. The project link
is in `coach/COACH.md`.

**Read the source.** Open the project in a new tab, open the file in the
editor, and run this in the page:

```js
document.querySelector('.cm-content').cmView.view.state.doc.toString()
```

Long files can come back cut short. If so, read the document as lines and
fetch it in slices:

```js
const d = document.querySelector('.cm-content').cmView.view.state.doc;
d.lines                         // how many
d.sliceString(d.line(1).from, d.line(120).to)
```

**Write the source.** Replace the whole file in one edit:

```js
const v = document.querySelector('.cm-content').cmView.view;
v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: NEW_TEXT } });
```

where `NEW_TEXT` is the file contents as a JSON string literal (so backslashes
survive). Read it back and compare lengths before going on. If the editor
internals differ and this fails, fall back to method 3; don't type a whole
file key by key.

**A tailored résumé gets its own file** in the Overleaf project (for example
`northwind_data_analyst.tex`, created with New File), set as the main document
from the Menu while it is being built. Never overwrite the master with a
tailored version.

**Compile.** Click Recompile, wait, and read the log panel for errors. Take a
screenshot of the preview and look at it.

**Get the PDF.** Ask the owner to click Download PDF (downloading is their
click). Then move the file from their Downloads folder into the application
folder under the upload name and run the checker on it.

## 3. By hand

If there is no browser control: save the `.tex` on disk, ask the owner to
paste it into Overleaf, compile, and download the PDF into the application
folder. Then run the checker.

## The check loop

After every compile:

```
python tools/check_resume.py <file.pdf> --tex <file.tex>      # tailored résumé
python tools/check_resume.py <letter.pdf> --letter            # cover letter
python tools/check_resume.py <master.pdf> --master            # master résumé
```

Fix what it reports, recompile, run it again. Expect several rounds to get
every bullet to one full line; that is normal. Stop when it passes and the
page looks right.

## LaTeX habits that prevent rework

- Start from `templates/resume/`. Don't change the preamble to make something
  fit.
- Escape `& % $ # _` in content.
- ASCII only in content; no accented letters.
- `--` with spaces around it in headings; plain `-` in date ranges.
- Write helper scripts to a file and run them. Shell here-documents can eat
  LaTeX backslashes.
