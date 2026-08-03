# Plan stabilizacji i modularyzacji Adaptive Cover rako Edition

## Status dokumentu

- Data utworzenia: 2026-07-26
- Data zakończenia wdrożenia: 2026-07-29
- Stan bazowy: `1.5.6`
- Wersja wynikowa: `1.6.0`
- Status: zakończony; weryfikacja statyczna i 101 testów, w tym testy na
  Home Assistant 2026.7.4, zakończone powodzeniem.
- Zakres: poprawność działania, kolejność decyzji, odporność asynchroniczna,
  podział dużych modułów i testy integracyjne.
- Pierwszeństwo: ten plan należy wykonać przed kolejnymi funkcjami opisanymi w
  `PLAN_ROZWOJU.md`.

## Cel

Integracja ma podejmować jedną jednoznaczną decyzję, przepuszczać ją przez jedną
bramkę wykonawczą i dopiero wtedy wysyłać polecenie do napędu. Każde zdarzenie
powinno być przetworzone albo jawnie zastąpione nowszym zdarzeniem, a diagnostyka
ma pokazywać dokładnie tę samą kolejność, którą wykonuje kod.

Docelowo `coordinator.py` ma odpowiadać wyłącznie za orkiestrację:

1. zebranie aktualnych danych;
2. wywołanie silnika decyzji;
3. przekazanie decyzji do polityk wykonawczych;
4. publikację wyniku i diagnostyki.

## Poza zakresem

- dwuosiowe żaluzje;
- zmiana sposobu konfiguracji istniejących wpisów bez migracji;
- nowe funkcje komfortowe przed zakończeniem stabilizacji;
- jednoczesne przepisywanie całej integracji;
- zmiana znaczenia `0%` i `100%`;
- kopiowanie architektury innego dodatku bez dopasowania do obecnego kodu.

## Problemy potwierdzone w przeglądzie

| ID | Priorytet | Problem | Skutek |
| --- | --- | --- | --- |
| S1 | P1 | Koniec nocnego wietrzenia ustawia pozycję nocną poza arbitrem decyzji | Deszcz lub wiatr może zostać nadpisany pozycją komfortową |
| S2 | P1 | Flaga `state_change` może zostać wyzerowana po nadejściu nowszego zdarzenia | Aktualna decyzja może zostać obliczona, lecz niewykonana |
| S3 | P2 | Retry porównuje cel BehavioralLearner z nieskorygowanym `self.state` | Wyuczony cel nie jest ponawiany |
| S4 | P2 | Niedostępna encja końca nie przechodzi na źródło zapasowe | Harmonogram może działać bez końca |
| S5 | P2 | Retry deszczu i wiatru podlega limitom ruchu | Pozycja awaryjna może nie zostać ponowiona |
| S6 | P3 | Priorytety diagnostyczne nie odpowiadają kolejności limitów pozycji | `decision_trace` może błędnie wyjaśniać zwycięzcę |
| S7 | P3 | Encja czasu manual override nie obsługuje wszystkich wartości z formularza | Widoczna wartość może różnić się od zapisanej |
| S8 | P3 | Testy koordynatora kontrolują głównie strukturę AST | Nie wykrywają wyścigów i rzeczywistej kolejności asynchronicznej |

## Zasady przebudowy

1. Najpierw naprawiamy błędy w obecnej strukturze, dopiero potem przenosimy kod.
2. W każdym momencie repozytorium ma zawierać działającą, testowalną integrację.
3. Jeden commit powinien rozwiązywać jeden problem albo wydzielać jeden moduł.
4. Żaden moduł poza wykonawcą ruchu nie może wywoływać usług domeny `cover`.
5. Decyzja bezpieczeństwa nie może zostać nadpisana przez timer, retry ani
   funkcję komfortową.
6. Moduły domenowe nie importują `coordinator.py`.
7. Home Assistant pozostaje warstwą wejścia/wyjścia; obliczenia i polityki mają
   być testowalne bez uruchamiania całego HA.
8. Każdy etap aktualizuje testy, README oraz `CHANGELOG.md`.
9. Formatowanie jest wykonywane tylko w plikach dotkniętych danym etapem.
10. Eksport ustawień i diagnostyki musi pozostać zgodny wstecznie.

## Docelowy podział plików

```text
custom_components/adaptive_cover/
|-- __init__.py                 # rejestracja integracji, usług i platform
|-- coordinator.py              # orkiestracja jednego cyklu aktualizacji
|-- coordinator_pipeline.py     # fazy snapshotu, decyzji i publikacji
|-- coordinator_events.py       # zdarzenia, generacje i cykl życia
|-- coordinator_execution.py    # polityki wykonawcze
|-- coordinator_data.py         # snapshot wejść z Home Assistant
|-- models.py                   # modele runtime i dane zdarzeń
|-- decision.py                 # DecisionResult, priorytety i czyste helpery
|-- geometry.py                 # geometria słońca i typy osłon
|-- climate.py                  # dane klimatyczne i wybór pozycji komfortowej
|-- schedule.py                 # źródła czasu, nocne wietrzenie i timery
|-- movement.py                 # wykonanie poleceń, limity, weryfikacja i retry
|-- manual_control.py           # ręczne przejęcie i historia ruchów użytkownika
|-- learning.py                 # BehavioralLearner i trwały zapis preferencji
|-- diagnostics.py              # punkt wejścia diagnostyki HA
|-- diagnostic_helpers.py       # serializacja i bezpieczne snapshoty
|-- config_flow.py              # tworzenie i edycja konfiguracji
|-- const.py                    # stałe i domyślne opcje
|-- options.py                  # normalizacja, walidacja i migracje opcji
|-- sensor.py
|-- binary_sensor.py
|-- switch.py
|-- number.py
|-- select.py
|-- time.py
|-- button.py
|-- sun.py
`-- helpers.py
```

### Dozwolony kierunek zależności

```text
encje HA / __init__
        |
        v
   coordinator
   /    |     \
schedule movement climate
   |       |      |
 models  manual  geometry
    \      |      /
      decision/helpers
```

`movement.py`, `schedule.py`, `climate.py` i `geometry.py` nie mogą importować
koordynatora. Koordynator składa te elementy i przekazuje im wymagane zależności.

## Etap 0: Zamrożenie kontraktów

### Cel

Przed zmianą zachowania zapisać w testach oczekiwaną kolejność i przygotować
minimalny symulator cyklu Home Assistant.

### Zadania

1. Dodać lekkie atrapy:
   - magazynu stanów;
   - rejestru usług;
   - zegara lokalnego i UTC;
   - `ConfigEntry`;
   - zdarzeń zmiany stanu.
2. Testować wynik obliczeń i listę wywołań usług, a nie tekst źródła przez AST.
3. Zachować obecne testy AST tymczasowo jako ochronę migracji.
4. Dodać macierz scenariuszy:
   - zwykłe słońce;
   - deszcz podczas ruchu;
   - wiatr podczas zakończenia nocnego wietrzenia;
   - otwarte okno;
   - manual override;
   - restart przed i po terminie;
   - niedostępny czujnik;
   - wyuczony offset pozycji;
   - zmiana celu podczas oczekiwania retry.

### Pliki

- `tests/fakes.py`
- `tests/test_runtime_order.py`
- `tests/test_movement_runtime.py`
- `tests/test_schedule_runtime.py`

### Kryteria zakończenia

- test potrafi wykazać kolejność: zdarzenie -> decyzja -> blokady -> usługa;
- problemy S1-S5 mają testy, które przed naprawą kończą się błędem;
- żaden test nie czeka rzeczywistych 45-300 sekund.

## Etap 1: Naprawy krytyczne bez przenoszenia kodu

### Etap 1A: Jeden arbiter dla zakończenia nocnego wietrzenia

1. Usunąć bezpośrednie ustawianie `sunset_position` z callbacku timera.
2. Callback ma oznaczyć przyczynę odświeżenia i uruchomić świeżą decyzję.
3. Aktualne deszcz, wiatr i polityka okna mają zostać ocenione przed wysłaniem
   polecenia.
4. Pominięty termin po restarcie ma używać tej samej ścieżki.
5. Diagnostyka ma zapisać `trigger = night_purge_deadline`.

Kryterium: podczas wiatru timer nie może wysłać pozycji nocnej, jeżeli aktualna
pozycja awaryjna jest inna.

### Etap 1B: Kolejka przyczyn odświeżenia

1. Zastąpić współdzielone flagi `state_change`, `first_refresh` i
   `timed_refresh` generacją lub zbiorem oczekujących przyczyn.
2. Przyczynę pobierać i usuwać przed pierwszym `await`.
3. Zdarzenie przychodzące podczas wykonywania starszego cyklu pozostaje
   oczekujące.
4. Kilka zdarzeń może zostać scalonych, ale najnowszy stan musi zostać wykonany.
5. Stare cele nie mogą być wysyłane do kolejnych rolet po zmianie decyzji na
   awaryjną.

Kryterium: nowsze zdarzenie pomiędzy dwiema roletami zatrzymuje pozostały stary
cel, pozostaje w kolejce i jest wykonywane w następnym cyklu.

### Etap 1C: Spójne cele i retry

1. Zapisać finalny cel osobno dla każdej rolety.
2. Retry porównuje cel z `_target_for_entity()`, nie z bazowym `self.state`.
3. Identyfikator generacji unieważnia starsze polecenie.
4. Deszcz i wiatr omijają cooldown oraz limity także podczas retry.
5. Retry ponownie ocenia okno, automatykę i ręczne przejęcie.

Kryterium: cel bazowy `40%` z biasem `+5%` jest weryfikowany i ponawiany jako
`45%`.

### Etap 1D: Bezpieczne źródła harmonogramu

1. Wydzielić jawny łańcuch:
   - dostępna encja końca;
   - poprawne `end_time`;
   - zachód z `close_sunset_offset`.
2. Stan `unknown` lub `unavailable` uruchamia źródło zapasowe.
3. Diagnostyka pokazuje źródło, wartość surową i powód fallbacku.
4. Walidować `start_time`, `end_time` i czas nocnego wietrzenia przed runtime.

Kryterium: niedostępna encja końca nie wyłącza harmonogramu.

### Wydanie po etapie 1

- proponowana wersja: `1.5.7`;
- osobne commity dla S1, S2, S3-S5 i S4;
- wymagany test na danych odpowiadających rzeczywistym ustawieniom domu.

## Etap 2: Modele i opcje

### `models.py`

Przenieść:

- `StateChangedData`;
- `AdaptiveCoverData`;
- model przyczyny odświeżenia;
- model finalnego celu rolety;
- model wyniku wykonania polecenia.

Modele nie mogą znać `HomeAssistant`, `ConfigEntry` ani koordynatora.

### `options.py`

Przenieść z `const.py`:

- `DEFAULT_OPTIONS`;
- `normalize_options`;
- `validate_options`;
- walidację czasu, zakresów, interpolacji i źródeł encji.

`const.py` pozostaje zbiorem stałych bez logiki biznesowej. Usunąć powtórzone
definicje `CONF_SUNSET_POS` i `CONF_SUNSET_OFFSET`.

### Kryteria zakończenia

- import `options.py` nie wymaga Home Assistant;
- testy walidacji obejmują błędne typy i brakujące wartości;
- import starych ustawień nadal przechodzi przez migrację bez utraty danych.

## Etap 3: Wydzielenie wykonawcy ruchu

### `movement.py`

Utworzyć `CoverMovementExecutor`, który odpowiada za:

- jedyne wywołanie `cover.set_cover_position` lub
  `cover.set_cover_tilt_position`;
- tolerancję pozycji;
- cooldown;
- limity godzinowe i dobowe;
- tryb Dry Run;
- generację poleceń;
- weryfikację celu;
- retry;
- anulowanie zadań przy unload;
- historię poleceń i błędów.

Wejście wykonawcy:

- encja;
- finalny cel;
- kod i poziom bezpieczeństwa decyzji;
- polityka okna;
- informacja o manual override;
- snapshot ustawień ruchu.

Wyjście:

- `executed`;
- `skipped`;
- `blocked`;
- `dry_run`;
- `failed`;
- dokładny kod powodu.

### Zasada bezpieczeństwa

Repozytorium ma zawierać dokładnie jedno miejsce z wywołaniem usługi domeny
`cover`. Test AST może pozostać tylko do pilnowania tej granicy.

### Kryteria zakończenia

- koordynator nie zarządza `verify_tasks`, `wait_for_target` ani
  `movement_history`;
- wszystkie ruchy, w tym timery i przycisk resetu, przechodzą przez wykonawcę;
- zadania retry są związane z cyklem życia wpisu konfiguracji.

## Etap 4: Wydzielenie harmonogramu

### `schedule.py`

Utworzyć:

- `ScheduleResolver` dla czystych obliczeń czasu;
- `ScheduleController` dla timerów Home Assistant.

Zakres:

- start zwykły;
- start Workday/Weekend;
- encja startu;
- encja końca;
- jawna godzina końca;
- zamknięcie solarne z przesunięciem;
- termin nocnego wietrzenia;
- termin manual override do zachodu;
- obsługa zmiany dnia i strefy czasowej;
- anulowanie timerów przy unload.

### Kryteria zakończenia

- wszystkie źródła czasu mają jedną opisaną kolejność;
- nie ma osobnej implementacji zachodu w koordynatorze, sensorze i manual
  override;
- sensor harmonogramu korzysta z tego samego wyniku co wykonanie;
- zmiana DST ma test dla dnia skróconego i wydłużonego.

## Etap 5: Rozdzielenie geometrii i klimatu

### `geometry.py`

Przenieść:

- `AdaptiveGeneralCover`;
- `AdaptiveVerticalCover`;
- `AdaptiveHorizontalCover`;
- `AdaptiveTiltCover`;
- `NormalCoverState`;
- obliczenia FOV, elewacji, blind spot i pozycji słońca.

### `climate.py`

Przenieść:

- `ClimateCoverData`;
- `ClimateCoverState`;
- deszcz i wiatr;
- klasyfikację temperatur;
- Strict Sun Block;
- Dawn Protection;
- Night Purge;
- Thermal Hold.

### Zmiana sposobu wyboru decyzji

Zamiast kolejnych wcześniejszych `return` każda reguła tworzy kandydata
`DecisionResult`. Arbiter wybiera najwyższy aktywny priorytet, a fizyczne limity
pozycji są osobnym etapem ograniczenia wyniku.

Proponowana kolejność:

1. wyłączone sterowanie;
2. polityka otwartego okna;
3. deszcz i wiatr;
4. ochrona przed zimnem;
5. ochrona przed świtem;
6. Strict Sun Block;
7. nocne wietrzenie;
8. fizyczne ograniczenie pozycji;
9. Thermal Hold;
10. tryb nocny, cień i automatyka komfortowa.

Priorytet numeryczny, kolejność kodu i `decision_trace` muszą być identyczne.

### Kryteria zakończenia

- `calculation.py` zostaje usunięty po przeniesieniu wszystkich klas;
- czyste obliczenia nie odczytują bezpośrednio `hass.states`;
- jeden snapshot wejść daje zawsze ten sam wynik;
- testy obejmują granice temperatur, progów światła i przejście dzień/noc.

## Etap 6: Ręczne przejęcie

### `manual_control.py`

Przenieść `AdaptiveCoverManager` i rozdzielić:

- wykrywanie ruchu użytkownika;
- termin wygaśnięcia;
- status rolet;
- historię wykonanych poleceń, która docelowo należy do `movement.py`.

### Zadania

1. Przycisk resetu sprawdza wynik powrotu do automatycznego celu.
2. Błąd usługi nie może być raportowany jako udany reset.
3. Encja wyboru czasu pokazuje wartość rzeczywiście zapisaną.
4. Dla wartości spoza listy formularz i encja nie mogą sobie przeczyć.
5. BehavioralLearner uczy się tylko po potwierdzonym ruchu użytkownika.

### Kryteria zakończenia

- ręczne przejęcie nie zależy od `wait_for_target` w koordynatorze;
- reset ma jawny wynik i kod błędu;
- testy obejmują ruch pośredni, zatrzymanie napędu i nieudany powrót.

## Etap 7: Odchudzenie koordynatora

Po zakończeniu ekstrakcji `coordinator.py` powinien zawierać:

1. inicjalizację zależności;
2. subskrypcje i odświeżenia;
3. utworzenie snapshotu wejść;
4. wywołanie arbitra decyzji;
5. przekazanie celu do wykonawcy;
6. publikację `AdaptiveCoverData`;
7. bezpieczny unload.

### Limity orientacyjne

- `coordinator.py`: maksymalnie około 500 linii;
- pojedyncza metoda: maksymalnie około 50 linii;
- brak bezpośrednich obliczeń geometrii i temperatur;
- brak bezpośrednich wywołań usług `cover`;
- brak ręcznego zarządzania retry.

## Etap 8: Spójność platform i dokumentacji

### Zadania

1. Ujednolicić typy i nazwy encji w `number.py`, `select.py` i `time.py`.
2. Dodać `translation_key` zamiast nazw zapisanych bezpośrednio po polsku.
3. Używać znormalizowanych opcji na wszystkich platformach.
4. Zaktualizować metadane `pyproject.toml` do repozytorium `rako79`.
5. Ujednolicić wersję Python/Home Assistant z faktycznie wspieranym wydaniem.
6. Sformatować etapami pliki wskazywane przez `ruff format --check`.
7. Usunąć nieaktualne komentarze i powielone helpery `state_attr` oraz
   `_as_float`.
8. Zaktualizować diagram przepływu w README.

### Kryteria zakończenia

- `ruff check` i `ruff format --check` przechodzą;
- metadane nie wskazują repozytorium oryginalnego autora jako aktywnego forka;
- polskie i angielskie tłumaczenia mają ten sam zestaw kluczy;
- diagnostyka i sensory używają tych samych nazw źródeł i kodów powodów.

## Etap 9: Testy integracyjne i wydanie

### Minimalny zestaw

1. Test konfiguracji i migracji starego wpisu.
2. Test startu Home Assistant i przeładowania integracji.
3. Test dwóch rolet z wydarzeniem pogodowym pomiędzy poleceniami.
4. Test unload podczas oczekiwania retry.
5. Test zmiany konfiguracji podczas aktywnego timera.
6. Test niedostępnych encji startu, końca, temperatury, światła i pogody.
7. Test pełnej macierzy priorytetów.
8. Test zgodności eksportu diagnostyki i ustawień.

### Wydanie

- proponowana wersja po pełnej modularyzacji: `1.6.0`;
- release notes rozdzielone na naprawy zachowania, architekturę i migracje;
- przed wydaniem test na kopii rzeczywistych ustawień wszystkich rolet;
- po instalacji nowy eksport diagnostyki i porównanie decyzji przez pełną dobę.

## Proponowana kolejność commitów

1. `test: dodaj testy rzeczywistej kolejności runtime`
2. `fix: zachowaj priorytety bezpieczeństwa przy końcu night purge`
3. `fix: nie gub zdarzeń podczas trwającego odświeżenia`
4. `fix: ujednolić finalny cel oraz retry BehavioralLearner`
5. `fix: dodać fallback źródła czasu zakończenia`
6. `refactor: wydziel modele runtime i walidację opcji`
7. `refactor: wydziel wykonawcę ruchów i retry`
8. `refactor: wydziel harmonogram oraz timery`
9. `refactor: wydziel geometrię i logikę klimatyczną`
10. `refactor: wydziel ręczne przejęcie`
11. `refactor: uprość koordynator`
12. `chore: ujednolić platformy, formatowanie i metadane`
13. `test: dodaj pełne testy integracyjne Home Assistant`
14. `docs: przygotuj dokumentację i wydanie 1.6.0`

## Kontrola po każdym etapie

1. `python tests/run_pytest.py -q`
2. `python -m ruff check custom_components tests`
3. `python -m ruff format --check custom_components tests`
4. `python -m compileall -q custom_components tests`
5. `git diff --check`
6. kontrola zgodności wersji w `const.py`, `manifest.json`, `pyproject.toml` i
   README;
7. sprawdzenie, czy żaden nowy kod nie wywołuje usług `cover` poza
   `movement.py`;
8. aktualizacja `CHANGELOG.md`.

## Definicja zakończenia

Plan jest zakończony, gdy:

- wszystkie problemy S1-S8 są naprawione i mają testy behawioralne;
- `coordinator.py` pełni wyłącznie rolę orkiestratora;
- timer, zdarzenie, retry i przycisk korzystają z tej samej bramki ruchu;
- żadna decyzja komfortowa nie nadpisuje aktualnej ochrony bezpieczeństwa;
- diagnostyka pokazuje rzeczywistą kolejność i finalny cel każdej rolety;
- integracja uruchamia się, przeładowuje i wyłącza bez pozostawionych zadań;
- testy, Ruff, formatowanie, `compileall` i `git diff --check` przechodzą;
- README PL/EN opisuje aktualną, a nie planowaną architekturę.

## Wynik końcowy

Weryfikacja z 2026-07-30:

- `101 passed` na Home Assistant `2026.7.4` i Python `3.14.5`;
- `ruff check`: bez błędów;
- `ruff format --check`: 44 pliki sformatowane;
- `compileall`: bez błędów;
- `git diff --check`: bez błędów białych znaków;
- `poetry check --lock`: lock zgodny z `pyproject.toml`;
- eksport ustawień z 2026-07-20: trzy rzeczywiste wpisy rolet zostały
  znormalizowane i zwalidowane bez błędów.

Instalacja wydania w docelowym Home Assistant i całodobowa obserwacja decyzji
są kontrolą eksploatacyjną po wdrożeniu, a nie brakującym elementem kodu.
