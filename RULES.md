# RULES.md — Zasady pracy z kodem

## 1. Przemyśl wszystko, zanim zaczniesz kodować
Sformułuj założenia, zapytaj w razie wątpliwości, porzuć wszelkie domysły.

## 2. Zacznij od najprostszego rozwiązania
Napisz tylko minimalny kod, który rozwiązuje problem, bez zbędnych abstrakcji.

## 3. Edytuj z chirurgiczną precyzją
Nie ruszaj kodu niezwiązanego z wymaganiami – każda zmieniona linijka jest powiązana z jasną specyfikacją.

## 4. Kieruj wykonaniem, kierując się celem
Zanim napiszesz pierwszą linijkę kodu, zamień niejasne instrukcje na weryfikowalne kryteria sukcesu.

## 5. Empiryczna weryfikacja to absolutny wymóg
Nigdy nie deklaruj ukończenia zadania na podstawie samego "poprawnego wyglądu" kodu. Agent ma kategoryczny zakaz zamykania zadania bez fizycznego uruchomienia kodu, weryfikacji logów i przetestowania zmodyfikowanej ścieżki w działającym środowisku. Zgadywanie wyników na sucho jest surowo zabronione.

## 6. Weryfikacja Nienaruszalnych Reguł (Guardrails Check)
Przed zatwierdzeniem jakiejkolwiek zmiany (zwłaszcza w obszarach takich jak czyszczenie, zapis plików czy routowanie), upewnij się, że modyfikacja nie łamie krytycznych reguł opisanych w `SOUL.md` (np. retencji plików graficznych, separacji środowisk na portach). Brak regresji musi zostać potwierdzony, a nie tylko założony.

## 7. Bezwzględny obowiązek czytania dokumentacji i ZAKAZ "wygładzania"
Zanim dotkniesz jakiejkolwiek funkcji lub usuniesz "przestarzały" kod w celu refaktoryzacji, masz BEZWZGLĘDNY OBOWIĄZEK przeczytać pliki `rules.md`, `soul.md` oraz wszystkie wpisy w folderze `knowledge`. ZAKAZ "REFAKTORYZACJI PRZY OKAZJI" (Boy Scout Rule). Jeśli naprawiasz błąd X, dotykaj TYLKO linii związanych z błędem X. Nigdy nie upraszczaj, nie czyść i nie usuwaj sąsiadującej logiki (np. fallbacków), chyba że zostało to wprost zlecone. Jeśli nie rozumiesz, po co dana linia tam jest - załóż, że obsługuje edge-case i zostaw ją w spokoju.

## 8. Nienaruszalność Bazy Danych (Bulletproof Database)
Aktywna produkcyjna baza (oraz jej zrzuty bezpieczeństwa) ZAWSZE rezyduje całkowicie poza przestrzenią repozytorium (obecnie `~/.cradle_data/`). Ponadto zrzuty bazy (backupy) używają niezmiennej flagi OS (`uchg`), która zabrania ich usunięcia przez polecenie RM lub biblioteki os. Nigdy nie przenoś bazy z powrotem do folderów Git'a i nie pisz skryptów omijających te flagi w sposób niezgodny z zasadami opisanymi w `knowledge/bulletproof_database.md`. Zawsze najpierw zapoznaj się z tym dokumentem przed ingerencją w mechanizmy składowania.
