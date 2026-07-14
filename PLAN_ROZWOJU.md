# Plan rozwoju Adaptive Cover rako Edition

## Cel

Plan opisuje rozwój po wydaniu `v1.5.1`. Wykorzystuje wybrane pomysły z
Adaptive Cover Pro, lecz nie zakłada kopiowania całej integracji ani jej kodu.
Każdy etap ma zostać dostosowany do istniejącego silnika decyzji, obecnych
rolet oraz danych diagnostycznych z tego domu.

Najważniejszy cel pozostaje niezmienny: automatyka ma być przewidywalna,
wyjaśnialna i bezpieczna dla napędów.

## Stan bazowy

Aktualna integracja zapewnia:

- geometrię słońca dla rolet, markiz i osłon z uchyłem;
- tryb klimatyczny, Strict Sun Block, ochronę termiczną i nocne wietrzenie;
- cztery polityki dla otwartego okna lub drzwi;
- manual override, cooldown, limity godzinowe i dobowe ruchów;
- weryfikację pozycji oraz retry działające w tle;
- `DecisionResult`, ślad decyzji i diagnostykę v4;
- eksport/import ustawień oraz trwały `BehavioralLearner`.

## Zasady dla wszystkich etapów

1. Każda nowa reguła zwraca `DecisionResult` z kodem, priorytetem,
   uzasadnieniem i danymi wejściowymi widocznymi w diagnostyce.
2. Żadna funkcja nie wywołuje `cover.set_cover_position` poza istniejącą
   bramką koordynatora odpowiedzialną za limity i weryfikację ruchu.
3. Bezpieczeństwo pogodowe, otwarte okno i manual override zawsze mają
   pierwszeństwo przed funkcjami komfortu.
4. Ustawienia muszą być walidowane, eksportowalne i importowalne. Zmiana
   formatu wymaga migracji `ConfigEntry` bez utraty danych.
5. Nowa funkcja jest wyłączona domyślnie albo zabezpieczona własnym
   przełącznikiem. Aktualizacja nie może zmienić zachowania istniejących rolet.
6. Każdy etap kończy się testami, tłumaczeniami PL/EN, dokumentacją i wpisem
   w `CHANGELOG.md`.

## Etap 1: Strefy olśnienia

### Cel

Chronić konkretne miejsca w pokoju przed bezpośrednim słońcem: telewizor,
monitor, biurko, łóżko lub stół. Roleta ma zejść niżej tylko wtedy, gdy promień
słońca może faktycznie dotrzeć do wskazanego miejsca.

### Zakres pierwszej wersji

Pierwsza wersja obsługuje punkt w osi okna. To celowe ograniczenie: zapewnia
realną korzyść dla rolet pionowych bez budowania modelu 3D całego pokoju.

Każda strefa zawiera:

- `name`: nazwa widoczna w ustawieniach i diagnostyce;
- `distance_m`: odległość chronionego punktu od szyby;
- `height_m`: wysokość punktu nad podłogą;
- `required_shade_percent`: minimalne przesłonięcie wymagane do ochrony;
- `enabled`: możliwość tymczasowego wyłączenia;
- `priority`: kolejność stref o różnych wymaganiach.

Algorytm sprawdza, czy promień słońca przechodzący przez okno może trafić w
punkt strefy. Jeśli tak, wyznacza najniższą wymaganą pozycję rolety, a wynik
ogranicza przez `min_position`, `max_position` i bieżące reguły bezpieczeństwa.

### Priorytet

Strefa olśnienia działa przed zwykłym śledzeniem słońca, ale po bezpieczeństwie
i ręcznym sterowaniu:

1. deszcz, wiatr i blokady fizyczne;
2. polityka otwartego okna;
3. manual override i tymczasowe blokady;
4. harmonogram oraz wymuszenia czasowe;
5. strefa olśnienia;
6. klimat, Strict Sun Block i standardowa geometria słońca.

### Zmiany techniczne

- dodać model `GlareZone` i walidator;
- rozszerzyć domyślne opcje, import, eksport i migrację wpisów;
- dodać osobny formularz zarządzania strefami w `config_flow.py`;
- umieścić czystą geometrię w `decision.py` albo `calculation.py`;
- umieścić zwycięską strefę, wymagane przesłonięcie i odrzucone strefy w
  `DecisionResult.inputs` oraz diagnostyce v4;
- dodać tłumaczenia i opis w README.

### Kryteria akceptacji

- nieaktywna strefa nie zmienia pozycji rolety;
- aktywna strefa nie omija limitów ruchu;
- manual override, deszcz, wiatr i okno mają pierwszeństwo;
- eksport/import zachowuje strefy;
- testy obejmują brak słońca, jedną i wiele stref, granice wysokości oraz
  konflikt z manual override.

### Dalszy rozwój

Po zebraniu diagnostyki można dodać przesunięcie boczne, szerokość strefy i
obsługę kilku okien. Nie należy tego wdrażać przed sprawdzeniem wersji prostej.

## Etap 2: Panel Lovelace „Stan rolet”

### Cel

Umożliwić codzienny podgląd automatyki bez otwierania eksportu diagnostycznego.
Panel ma odpowiadać na pytanie: „co robi roleta, dlaczego i czy może się teraz
poruszyć?”.

### Zakres pierwszej wersji

Pierwsza wersja będzie gotowym widokiem Lovelace zbudowanym ze standardowych
kart Home Assistant. Nie wymaga własnego kodu JavaScript ani nowej zależności.

Dla każdej grupy pokazuje:

- aktualną i docelową pozycję;
- stan automatyki oraz kod zwycięskiej decyzji;
- aktywną ochronę: deszcz, wiatr, zimno, słońce, okno lub manual override;
- temperaturę, promieniowanie i stan nocnego wietrzenia;
- wykorzystanie limitów ruchu;
- przyciski resetu manual override i BehavioralLearner;
- aktywną strefę olśnienia po wdrożeniu etapu 1.

### Zmiany techniczne

- zdefiniować niewielki, stabilny zestaw atrybutów panelu;
- dodać do README przykładowy YAML dashboardu;
- utrzymać odczytowy charakter panelu; przyciski mogą wywoływać tylko obecne,
  bezpieczne akcje;
- dopiero po potwierdzeniu użyteczności rozważyć osobną kartę HACS w osobnym
  repozytorium frontendowym.

### Kryteria akceptacji

- panel jest czytelny na telefonie i tablecie;
- stan panelu zgadza się z `DecisionResult` oraz diagnostyką v4;
- brak danych czujnika jest jawnie opisany, a nie udawany jako decyzja;
- otwarcie panelu nie uruchamia ruchu rolet ani dodatkowego odświeżania sprzętu.

## Etap 3: Bezpieczne tryby tymczasowe

### Cel

Pozwolić automatyzacjom przekazać krótkotrwały zamiar użytkownika bez trwałego
wyłączania algorytmu i bez wielu niezależnych automatyzacji walczących o roletę.

### Proponowane tryby

- `tv`: zwiększona ochrona ekranu przez strefę olśnienia;
- `sleep`: prywatność do ustalonej godziny albo wschodu;
- `privacy`: pozycja prywatności z czasem wygaśnięcia;
- `ventilation`: pozycja wietrzenia tylko przy spełnionych warunkach;
- `none`: usuwa wymuszenie i zwraca sterowanie automatyce.

Pozycje nie są zakodowane na stałe. Każdy tryb używa konfiguracji danego wpisu
lub przekazanej, zwalidowanej pozycji.

### Minimalny zestaw usług

- `adaptive_cover.set_temporary_mode`;
- `adaptive_cover.set_temporary_position`;
- `adaptive_cover.clear_temporary_override`.

Usługi przyjmują `entry_id` albo jednoznaczną nazwę wpisu i opcjonalny czas
wygaśnięcia. Nie sterują roletą bezpośrednio, tylko przekazują zamiar do
standardowego pipeline decyzji.

### Zmiany techniczne

- przechowywać stan tymczasowy per `ConfigEntry` wraz z czasem wygaśnięcia;
- zaplanować świeżą decyzję dokładnie w chwili wygaśnięcia;
- ujawnić stan, źródło i pozostały czas w diagnostyce;
- walidować konflikt z oknem, pogodą, manual override i limitami;
- nie tworzyć wielu równoległych timerów po ponownym ustawieniu trybu.

### Kryteria akceptacji

- wygaśnięcie zawsze uruchamia świeżą decyzję;
- `ventilation` nie omija ochrony pogodowej;
- manual override nadal zatrzymuje automatykę;
- testy obejmują wygasanie, restart i konflikty priorytetów.

## Etap 4: Formalny arbiter sezonowy

### Cel

Uczytelnić aktualną logikę klimatyczną przez rozdzielenie strategii, bez
automatycznego zmieniania zachowania rolet po aktualizacji.

### Strategie

- ogrzewanie zimowe: wykorzystanie energii słonecznej w chłodnym pokoju;
- izolacja zimowa: ograniczenie strat po zachodzie lub przy niskiej temperaturze;
- chłodzenie letnie: ochrona przed przegrzewaniem;
- komfort przeciwolśnieniowy: ochrona stref użytkowych niezależnie od temperatury;
- okres przejściowy: łagodne pozycjonowanie geometryczne.

### Warunek rozpoczęcia

Etap rozpoczynamy dopiero po zebraniu eksportów diagnostyki v4 z działającymi
strefami olśnienia i opisaniu rzeczywistych przypadków, których obecne reguły
nie wyjaśniają. Nie refaktoryzujemy tylko po to, by przypominać inną integrację.

### Zmiany techniczne i kryteria

- zachować aktualne zachowanie jako testy regresji;
- oddzielić klasyfikację sezonu od wyboru pozycji i ruchu silnika;
- dodać odrębne kody `DecisionResult` i przełączniki funkcji;
- nie dopuścić do oscylacji ogrzewanie/chłodzenie;
- przetestować granice temperatur, zachód, nocne wietrzenie i brak danych.

## Celowo poza planem

- kopiowanie całego pipeline Adaptive Cover Pro;
- wiele usług zmieniających dowolne parametry bez walidacji;
- zmiana domeny `adaptive_cover`, która wymagałaby migracji encji;
- równoległe sterowanie jedną roletą przez dwie integracje;
- rozwój sekwencera dwuosiowych żaluzji;
- funkcje bez potwierdzenia w diagnostyce realnego domu.

## Kolejność wydań

| Wydanie orientacyjne | Zakres | Warunek przejścia dalej |
| --- | --- | --- |
| `1.6.x` | Strefy olśnienia v1 | Testy geometrii oraz eksporty z rzeczywistych pomieszczeń. |
| `1.6.x` lub `1.7.x` | Dashboard YAML i stabilne atrybuty | Brak rozbieżności względem diagnostyki v4. |
| `1.7.x` | Tryby tymczasowe i trzy usługi | Bezpieczne wygasanie oraz brak obejścia ograniczeń. |
| `1.8.x` | Arbiter sezonowy za przełącznikami funkcji | Brak regresji względem scenariuszy klimatycznych. |

## Procedura dla każdego etapu

1. Zdefiniować problem na podstawie eksportu diagnostyki lub scenariusza domu.
2. Spisać priorytet nowej decyzji względem bezpieczeństwa i manual override.
3. Dodać model opcji, walidację, migrację i tłumaczenia.
4. Dodać czystą logikę decyzji oraz testy granic.
5. Podłączyć ją do koordynatora bez omijania ograniczeń ruchu.
6. Rozszerzyć diagnostykę v4 oraz przetestować jedną roletę w `dry_run`.
7. Po obserwacji na rzeczywistych roletach przygotować release z opisem
   zachowania, ryzyk i sposobu wyłączenia funkcji.

## Weryfikacja przed release

- uruchomić Ruff dla `custom_components/adaptive_cover` i `tests`;
- uruchomić wszystkie testy jednostkowe;
- uruchomić `compileall` dla integracji i testów;
- sprawdzić `git diff --check` oraz poprawność JSON manifestu, usług i tłumaczeń;
- przetestować nową funkcję na jednej rolecie z aktywnym `dry_run`.
