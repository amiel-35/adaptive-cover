# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - 2026-07-14

### Zmienione
- [Zmienione] Podniesiono wersję integracji do `1.5.4` po analizie rzeczywistej sekwencji rozruchowej Home Assistant 2026.7.
- [Zmienione] Ujednolicono priorytety wykonania: deszcz i wiatr omijają harmonogram, ręczne przejęcie, cooldown i limity ruchów, a pozostałe zabezpieczenia omijają harmonogram z zachowaniem ochrony silnika.
- [Zmienione] Uporządkowano pierwszeństwo źródeł czasu; `start_time` działa bez encji Workday, a `close_sunset_offset` jest dostępny tylko przy zamknięciu solarnym.

### Dodane
- [Dodane] BehavioralLearner zapisuje ostatni czas bezpośredniego nasłonecznienia z ograniczeniem częstotliwości zapisu, dzięki czemu Thermal Hold zachowuje kontekst po restarcie.
- [Dodane] Rozszerzono testy regresyjne o priorytety bezpieczeństwa, pominięte terminy, stany pośrednie silnika, trwałość uczenia, walidację czasu oraz interpolacji.

### Naprawione
- [Naprawione] Zakończenie nocnego wietrzenia wykonuje teraz rzeczywiste zamknięcie rolety do skonfigurowanej pozycji nocnej, niezależnie od późniejszego startu dziennego harmonogramu, z zachowaniem ochrony otwartego okna i aktywnego sterowania ręcznego.
- [Naprawione] Restart między końcem nocnego wietrzenia a startem dziennego harmonogramu nadrabia pominięte zamknięcie zamiast pozostawiać roletę w pozycji przewietrzania.
- [Naprawione] Pierwsze sterowanie odbywa się dopiero po odtworzeniu przełączników `RestoreEntity`, więc automatyka nie czeka na kolejne zdarzenie czujnika po uruchomieniu Home Assistant.
- [Naprawione] Ręczne włączenie automatyki najpierw przelicza aktualny cel i korzysta ze wspólnej ścieżki priorytetów zamiast blokować decyzje bezpieczeństwa własnym sprawdzeniem harmonogramu.
- [Naprawione] Wcześniejsza zmiana godziny końca oraz termin pominięty podczas restartu są wykonywane, zamiast pozostawać za starym zaplanowanym callbackiem.
- [Naprawione] `manual_ignore_intermediate` zatrzymuje obsługę stanów `opening` i `closing` przed uruchomieniem detekcji ręcznego sterowania.
- [Naprawione] Ręczne przejęcie używa stałego terminu końcowego; wariant „do zachodu słońca” nie kończy się w połowie pozostałego czasu.
- [Naprawione] BehavioralLearner nie uczy się z ręcznych zmian powstałych przy aktywnych decyzjach bezpieczeństwa.
- [Naprawione] Zmiana encji pogody nie zwraca prognozy zapamiętanej dla poprzedniej encji, gdy nowe źródło jest niedostępne.
- [Naprawione] Niejednoznaczna dzienna godzina końca nocnego przewietrzania nie aktywuje przewietrzania przez cały dzień.
- [Naprawione] Interpolacja obsługuje wartość początkową `0`, odrzuca powtarzające się punkty oraz wartości poza zakresem `0...100`.
- [Naprawione] Niedostępna encja Workday zachowuje bezpieczne założenie dnia roboczego zamiast przełączać harmonogram na weekendowy.
- [Naprawione] Strict Sun Block nie interpretuje już `null`, `unknown` ani `unavailable` z czujnika irradiancji/lux jako silnego słońca; wymaga aktualnego odczytu większego od progu włączenia.
- [Naprawione] Zdarzenia czujników i przejściowe stany przełączników podczas fazy `STARTING` mogą aktualizować obliczenia, ale nie wysyłają poleceń do rolet. Pierwszy ruch następuje dopiero po zdarzeniu pełnego uruchomienia HA i krótkiej stabilizacji encji.
- [Naprawione] Diagnostyka pokazuje stan `runtime_initialized` oraz źródło, wartość, próg i dostępność sygnału Strict Sun Block, co pozwala odróżnić prawdziwe silne słońce od brakującego odczytu.

## [Unreleased] - 2026-07-13

### Zmienione
- [Zmienione] Podniesiono wersję integracji do `1.5.1`, aby wdrożenie poprawki przepływu konfiguracji było jednoznacznie widoczne w Home Assistant i diagnostyce.
- [Zmienione] Przygotowano fork `Adaptive Cover rako Edition` do dystrybucji przez HACS: zaktualizowano nazwę, właściciela, dokumentację, obsługę zgłoszeń, szablony GitHub i release notes.
- [Zmienione] Zachowano domenę `adaptive_cover`, aby aktualizacja nie wymagała migracji istniejących wpisów konfiguracji ani encji Home Assistant.
- [Zmienione] Dokumentacja HACS ostrzega przed równoległą instalacją innego wariantu o tej samej domenie `adaptive_cover`.

### Dodane
- [Dodane] Dodano zasób marki `brand/icon.png` oraz plik `NOTICE.md` z informacją o pochodzeniu kodu, licencji MIT i utrzymaniu forka przez `@rako79`.
- [Dodane] Dodano `PLAN_ROZWOJU.md` z priorytetami przyszłych zmian: strefy olśnienia, panel Lovelace, bezpieczne tryby tymczasowe i arbiter sezonowy.

### Usunięte
- [Usunięte] Usunięto przekierowanie finansowania do poprzedniego maintenera.
- [Usunięte] Usunięto z planu rozwoju obsługę dwuosiowych żaluzji.

### Naprawione
- [Naprawione] Przepływ opcji korzysta z `config_entry` udostępnianego przez Home Assistant dopiero po inicjalizacji, zgodnie z API HA 2026.7; otwarcie przycisku „Konfiguruj” nie kończy się już błędem 500.

## [Unreleased] - 2026-07-12

### Dodane
- [Dodane] Wprowadzono wspólny schemat diagnostyki v4 dla eksportu serwisowego i standardowej diagnostyki Home Assistant, obejmujący wersje środowiska, ścieżkę załadowanego komponentu i stan `ConfigEntry`.
- [Dodane] Dodano ograniczoną historię 50 decyzji i poleceń, ślad oceny reguł, zdrowie koordynatora, czasy odświeżeń, stan cache prognozy oraz szczegółowe metadane zadań retry.
- [Dodane] Diagnostyka pozycji pokazuje błąd względem celu, efektywną tolerancję i jednoznaczne `target_satisfied`.
- [Dodane] Diagnostyka BehavioralLearner pokazuje stan odczytu Store, ostatni błąd, ostatnią korektę użytkownika i czas zaplanowania zapisu.

### Zmienione
- [Zmienione] Podniesiono wersję integracji do `1.5.0`, aby diagnostyka jednoznacznie identyfikowała wdrożenie zawierające schemat v4 i poprawki runtime.
- [Zmienione] Przepisano `README.md` w kompletnych wersjach PL i EN zgodnie z aktualnym działaniem integracji 1.5.0, jej encjami, usługami, priorytetami, zabezpieczeniami i diagnostyką v4.
- [Zmienione] Eksport ustawień używa schematu v4 i zapisuje datę, wersję integracji, wersję HA, strefę czasową, wersję wpisu oraz wynik walidacji opcji.
- [Zmienione] Eksporty domyślnie dodają lokalną datę do nazwy pliku, a pola nazwy i przełączniki daty są aktywne domyślnie w formularzu usługi.
- [Zmienione] Diagnostyka domyślnie wykonuje ograniczone do 30 sekund odświeżenie read-only, które przelicza aktualny stan bez wysyłania poleceń ruchu, oraz rejestruje jego wynik i czas.

### Naprawione
- [Naprawione] Pozycje krańcowe `0%` i `100%` respektują teraz `delta_position`, dzięki czemu urządzenie raportujące np. `97%` nie otrzymuje bez końca poleceń ustawienia `100%`.
- [Naprawione] Weryfikacja i ponowienia ruchu używają tej samej tolerancji pozycji co główna automatyka, co zapobiega seriom zbędnych retry i fałszywemu osiąganiu limitu dobowego.
- [Naprawione] Status rolety jest odświeżany po osiągnięciu celu w granicach tolerancji i nie pozostaje błędnie jako `daily_move_limit` lub wcześniejsze pominięcie.
- [Naprawione] Obliczenia słońca używają `get_astral_observer` zamiast wycofanego `get_astral_location`, usuwając masowe ostrzeżenia kompatybilności przed Home Assistant 2027.7.
- [Naprawione] Zdarzenie zwrotne z silnika używa `delta_position`, więc niedokładna pozycja krańcowa nie jest błędnie rozpoznawana jako ręczne zatrzymanie rolety.
- [Naprawione] Opóźniona weryfikacja pozycji działa jako zadanie tła powiązane z `ConfigEntry`, dlatego oczekiwanie na retry nie blokuje zakończenia startu Home Assistant.
- [Naprawione] Platforma `diagnostics` jest ładowana wraz z pakietem integracji, zamiast wykonywać pierwszy import pliku w pętli zdarzeń Home Assistant.
- [Naprawione] Wersja Home Assistant w diagnostyce jest pobierana z `homeassistant.const`, zgodnie z aktualnym API, dzięki czemu import platformy nie przerywa ładowania całej integracji.

## [Unreleased] - 2026-07-11

### Dodane
- [Dodane] Ukończono trwały `BehavioralLearner`: zapisuje per roleta ograniczone korekty pozycji i temperatury komfortu, odtwarza je po restarcie oraz udostępnia przycisk resetu uczenia.
- [Dodane] Dodano konfigurowalny czas `thermal_hold_duration` i różnicę temperatur `thermal_hold_release_delta` zwalniającą ochronę termiczną.
- [Dodane] Dodano czysty moduł decyzji oraz testy jednostkowe dla nocnego wietrzenia, ochrony termicznej i walidacji ustawień.
- [Dodane] Dodano typowany `DecisionResult` z kodem, priorytetem, uzasadnieniem i wejściami decyzji udostępnianymi w diagnostyce.
- [Dodane] Dodano workflow CI uruchamiający Ruff i testy jednostkowe.

### Zmienione
- [Zmienione] Wszystkie opóźnione retry otrzymują numer generacji, ponownie sprawdzają aktualny cel, automatykę, okno, manual override i limity ruchu oraz są anulowane przy przeładowaniu integracji.
- [Zmienione] Eksport ustawień używa schematu 3, a import pozostaje zgodny ze starszym formatem i odrzuca cały plik przed zmianami, gdy wykryje niespójne opcje.
- [Zmienione] Starsze wpisy `ConfigEntry` są jawnie migrowane do wersji 2 z kompletem znormalizowanych i zwalidowanych opcji.
- [Zmienione] Diagnostyka HA i eksport JSON pokazują trwałe uczenie, cel per roleta, stres termiczny, ostatnie bezpośrednie słońce, bieżący powód statusu i błędy usług.
- [Zmienione] Prognoza pogody jest buforowana przez godzinę, a obliczenia pozycji słońca nie tworzą wielokrotnie tych samych zakresów czasu.
- [Zmienione] Blueprint integracji oznaczono jako legacy dla dodatkowych rolet i usunięto dublowanie encji sterowanych bezpośrednio przez integrację.

### Naprawione
- [Naprawione] `thermal_hold` działa wyłącznie po rzeczywistym bezpośrednim nasłonecznieniu danego okna i zwalnia osłonę, gdy chłodniejsze powietrze zapewnia wystarczające chłodzenie.
- [Naprawione] Globalne promieniowanie nie wymusza już ochrony termicznej w pokojach, których okna pozostają w cieniu.
- [Naprawione] Godzina końca nocnego wietrzenia jest twardą granicą także przed wschodem słońca i uruchamia świeżą decyzję zamiast bezwarunkowego zamknięcia.
- [Naprawione] Włączenie automatyki respektuje politykę otwartego okna, harmonogram, cooldown, limity ruchu i ręczne przejęcie sterowania.
- [Naprawione] Zabezpieczono obliczenia markiz i lameli przed dzieleniem przez zero, `NaN` i wartościami spoza zakresu `0-100%`.
- [Naprawione] Obsłużono brak pozycji i niepełne zdarzenia rolet bez błędnego rozpoznawania manual override.
- [Naprawione] Prędkość wiatru jest normalizowana z `m/s`, `mph` i węzłów do `km/h` przed porównaniem z progiem bezpieczeństwa.
- [Naprawione] Status metody sterowania wraca do `intermediate`, a sensor harmonogramu pokazuje stan rzeczywisty zamiast stałego `Aktywny`.

## [Unreleased] - 2026-06-27

### Naprawione
- [Naprawione] Status algorytmu pokazuje teraz wyłączoną automatykę zamiast nieaktualnego powodu wyliczonej pozycji.
- [Naprawione] Uzupełniono listę stanów sensora algorytmu o `control_disabled` i brakujący `strict_sun_block`.
- [Naprawione] Koniec dziennego harmonogramu nie wymusza już pozycji `0%`, gdy aktywne jest nocne sterowanie klimatyczne.
- [Naprawione] Nocne wietrzenie i zabezpieczenia klimatyczne mogą reagować także poza godzinami dziennego harmonogramu.
- [Naprawione] Ruch wykonany przez dodatek nie jest już błędnie oznaczany jako ręczne sterowanie po osiągnięciu pozycji docelowej.
- [Naprawione] Dostępny fizyczny czujnik opadów ma pierwszeństwo przed prognozą pogody, co zapobiega cyklicznemu zamykaniu i otwieraniu rolet podczas nocnego wietrzenia.

### Dodane
- [Dodane] Dodano konfigurowalną godzinę zakończenia nocnego wietrzenia; rolety są wtedy zamykane na `0%`.
- [Zmienione] Ochrona przed świtem i poranna blokada słońca nie przerywają wietrzenia przed ustawioną godziną, jeśli nadal spełnione są warunki temperaturowe.

## [Unreleased] - 2026-06-18

### Naprawione
- [Naprawione] Dodano nazwę przełącznika `dry_run_toggle` jako `Tryb testowy`, aby nie wyświetlał się jako nazwa pomieszczenia.
- [Dodane] Rozszerzono `export_diagnostics` o `schema_version`, `configured_covers` oraz `cover_diagnostics` z czytelnym podsumowaniem każdej rolety.
- [Dodane] Dodano do atrybutów diagnostycznych surowe odczyty `inside_temperature`, `lux`, `irradiance`, `outside_temperature_entity`, `rain_rate`, `weather_state` i `wind_gust`.
- [Dodane] Dodano konfigurowalne utrzymanie ochrony termicznej po wyjściu słońca z zasięgu okna.
- [Dodane] Dodano przełącznik nocnego wietrzenia oraz suwak pozycji wietrzenia nocnego w ustawieniach klimatycznych.
- [Naprawione] Zmieniono blokadę `delta_time`, aby opierała się na ostatnim ruchu wykonanym przez dodatek, a nie na `last_updated` encji rolety w Home Assistant. Dzięki temu świeżo odświeżony stan rolety nie blokuje automatycznego domknięcia.
- [Naprawione] Poprawiono wybór temperatury bieżącej w logice klimatycznej: algorytm używa temperatury pokoju, a temperatury zewnętrznej tylko jako awaryjnego fallbacku.
- [Naprawione] Rozszerzono diagnostykę pominiętych ruchów o konkretny powód blokady, np. `time_delta_not_passed`, `manual_override_active` albo `position_delta_too_small`.
- [Naprawione] Poprawiono polskie opisy usług w `services.yaml`.

## [Unreleased] - 2026-05-26

### Dodane (Added)
- **PL:** Wdrożono **Explainable AI** – dodano nowy sensor `sensor.{type}_state_reason_{name}` opisujący powody podejmowanych decyzji przez algorytm.
- **EN:** Implemented **Explainable AI** – added a new `sensor.{type}_state_reason_{name}` entity describing the reasons behind algorithm decisions.
- **PL:** Dodano **Model Predictive Control (MPC)** – wbudowano predykcyjny model termiczny szacujący temperaturę za godzinę na podstawie nasłonecznienia (W/m2 / Lux).
- **EN:** Added **Model Predictive Control (MPC)** – built-in predictive thermal model estimating the room temperature in 1 hour based on solar irradiance (W/m2 / Lux).
- **PL:** Dodano moduł **Uczenia Nawyków (Behavioral ML)** bazujący na EMA (Exponential Moving Average), uczący się preferowanej pozycji rolet i temperatury po ręcznych zmianach użytkownika (`learning.py`).
- **EN:** Added **Behavioral ML** module using EMA (Exponential Moving Average) to learn preferred cover positions and comfort temperatures after manual overrides (`learning.py`).
- **PL:** Dodano usługi `adaptive_cover.export_config` i `adaptive_cover.import_config` pozwalające na zrzut i wgrywanie pełnej konfiguracji wszystkich rolet z/do pliku `adaptive_cover_settings.json` w katalogu `/config`. 
- **EN:** Added `adaptive_cover.export_config` and `adaptive_cover.import_config` services to export and import full configuration of all covers from/to `adaptive_cover_settings.json` file in the `/config` directory.
- **PL:** Dodano tryb **Strict Sun Block** – funkcja zamykająca rolety wyłącznie na podstawie bezpośredniego nasłonecznienia okna, jeśli dzień jest słoneczny. Posiada własny przełącznik w interfejsie.
- **EN:** Added **Strict Sun Block** mode – a feature that closes the blinds strictly based on direct sun exposure on the window during sunny days, equipped with its own dashboard switch.

### Zmienione / Poprawione (Changed / Fixed)
- **PL:** Zmieniono zachowanie domyślne na **Logikę Rozmytą (Fuzzy Logic)** – zamiast zachowania 0% / 100%, rolety zamykają i otwierają się płynnie w zależności od "Stresu termicznego".
- **EN:** Changed the default behavior to **Fuzzy Logic** – instead of 0% / 100% states, covers now adjust fluently based on the calculated "Thermal Stress".
- **PL:** Zmieniono logikę `is_summer` (letniego zamykania rolet) w `calculation.py`. Od teraz rolety zostaną zamknięte, gdy wewnątrz pomieszczenia robi się zbyt gorąco i słońce mocno grzeje (nasłonecznienie/lux przewyższa próg), niezależnie od tego czy na zewnątrz jest upał czy nie. 
- **EN:** Modified `is_summer` logic in `calculation.py`. The covers will now close when the inside temperature is too hot and the sun radiation/lux is above the threshold, ignoring the outside temperature condition.
- **PL:** Naprawiono błąd (Anti-Fighting Mechanism) polegający na ponawianiu komendy zamknięcia/otwarcia po tym, jak użytkownik zatrzymał roletę w połowie drogi (poprawna detekcja manual override).
- **EN:** Fixed an issue (Anti-Fighting Mechanism) where the system persistently retried moving the blind if the user manually stopped it midway (proper manual override detection).
- **PL:** Naprawiono nadpisywanie ręcznej blokady – odświeżanie czasowe np. przy zachodzie słońca (`timed_refresh`) respektuje teraz aktywne blokady przycisku na ścianie.
- **EN:** Fixed manual override bypass – timed refreshes (e.g., at sunset) now properly respect active manual wall switch blockades.
- **PL:** Naprawiono omijanie limitów `min_pos` i `max_pos` – od teraz krytyczne stany ochronne (deszcz, wiatr, blokada słońca) poprawnie respektują fizyczne limity zadane przez użytkownika, zamiast w ciemno wymuszać pozycję 0%.
- **EN:** Fixed `min_pos` and `max_pos` bypass – critical protective states (rain, wind, sun block) now properly respect physical limits set by the user instead of blindly forcing the 0% position.
- **PL:** Usunięto kodowanie "na sztywno" nazw encji (sensorów, przełączników, przycisków) w Pythonie. Wdrożono natywny mechanizm tłumaczeń Home Assistant oparty na plikach `pl.json` i `en.json`. 
- **EN:** Removed hardcoded entity names (sensors, switches, buttons) in Python. Implemented native Home Assistant translation mechanism using `pl.json` and `en.json`.
- **PL:** Zmodyfikowano usługę `import_config`, aby parowała zapisane ustawienia z nowymi instancjami po **nazwie urządzenia**, a nie po ukrytym kluczu `entry_id`. Umożliwia to poprawne odtworzenie konfiguracji nawet po całkowitym usunięciu i ponownym dodaniu integracji. Dodano również domyślną nazwę pliku `adaptive_cover_settings.json` dla usługi importu.
- **EN:** Modified `import_config` service to match stored settings with new instances using the **device title** rather than the hidden `entry_id`. This allows restoring configurations properly even after completely removing and re-adding the integration. Added a default filename `adaptive_cover_settings.json` to the import service schema.
