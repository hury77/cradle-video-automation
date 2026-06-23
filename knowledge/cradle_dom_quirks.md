# Cradle DOM Quirks & Extraction Rules

Ten plik zawiera krytyczną wiedzę (Knowledge Item) dotyczącą tego, jak strona Cradle buduje strukturę HTML dla załączników. Ignorowanie tych zasad prowadzi do błędów w rozszerzeniu `cradle-scanner.js`.

## 1. Nazwy plików obok tagu <a>, a nie wewnątrz
Cradle bardzo często umieszcza tekstową nazwę pliku w komórce `<td>`, bezpośrednio **OBOK** klikalnej ikonki, a nie wewnątrz tagu `<a>`. 

**Typowa struktura (ZŁA do .textContent):**
```html
<td>
  <a href="/media/cradle/comment/123456/download">
    <i class="fa-file"></i>
  </a>
  video_file.mp4
</td>
```
Jeśli użyjesz `link.textContent` na elemencie `<a>`, otrzymasz pusty ciąg znaków `""`. 
**Zawsze używaj:** `link.parentElement.textContent`, aby uzyskać dostęp do `"video_file.mp4"`.

## 2. Adresy URL bez rozszerzeń (nc-download)
Większość plików "Acceptance" i "Emission" udostępniana bezpośrednio przez platformę nie posiada rozszerzenia w URL (np. `.../12345/download`).
Nie polegaj wyłącznie na `filename.match(/\.[^.]+$/)`. Jeśli URL nie ma rozszerzenia, musisz:
1. Szukać hintu w `parentElement.textContent`.
2. Jeśli hintu nie ma (np. link w komentarzu `pm distribution`), należy zastosować fallback do domyślnego rozszerzenia (np. dopisanie `.mp4`). ZAKAZ USUWANA FALLBACKÓW.

## 3. Linki wewnątrz komentarzy (text content)
Czasem link do pobrania pliku jest ukryty w tekście komentarza:
```html
<p>Prośba o final files z <a href="https://cradle.egplusww.pl/assets/.../comments/">https://cradle...</a></p>
```
Zauważ, że tekst linku to sam URL. Nie ma tu słowa `.mp4` ani `.zip`. Skaner musi to przetrawić i przepuścić przez fallback, ponieważ bezpośredni URL rzuci się w oczy jako bezpieczny (brak jawnego `.png`/`.pdf`).
