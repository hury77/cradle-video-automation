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
