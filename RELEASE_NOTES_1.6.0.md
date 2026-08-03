# Adaptive Cover rako Edition 1.6.0

## Polski

Wydanie 1.6.0 kończy plan stabilizacji i modularyzacji. Najważniejsza zmiana
dotyczy kolejności działania: timer, zmiana sensora, ręczne sterowanie i retry
korzystają teraz z jednego arbitra decyzji oraz jednej bramki poleceń osłon.

### Naprawy zachowania

- koniec nocnego wietrzenia wybiera jawną pozycję nocną i nadal respektuje
  deszcz, wiatr, zimno oraz otwarte okno;
- ochrona przed zimnem używa histerezy `1°C`, która zapobiega nocnym
  przełączeniom przy wahaniach temperatury wokół progu;
- pośrednie i powtórzone raporty własnego ruchu nie uruchamiają ręcznego
  przejęcia ani BehavioralLearner;
- starsze korekty uczenia, które mogły powstać z takich raportów, są
  jednorazowo zerowane bez usuwania czasu ostatniego bezpośredniego słońca;
- słabe promieniowanie przy zerowym stresie termicznym przywraca pozycję
  domyślną mimo wysokiej prognozy temperatury;
- niedostępny skonfigurowany czujnik temperatury pomieszczenia nie jest
  zastępowany temperaturą zewnętrzną, więc nie tworzy fałszywego stresu
  termicznego i niemal pełnego zamknięcia;
- czas zachodu z Astral jest przeliczany z UTC na lokalną strefę Home Assistant
  przed rozpoczęciem nocnego przewietrzania;
- krótkie skoki czujnika zewnętrznego większe niż `3°C` są odrzucane, dopóki
  nowa wartość nie utrzyma się przez pięć minut;
- tryb nocny używa pozycji po zachodzie zamiast chwilowo przywracać dzienne
  `100%` przed rozpoczęciem przewietrzania;
- BehavioralLearner nie zapisuje ruchów wykonanych poza aktywnym harmonogramem,
  a migracja wersji `4` usuwa utworzone wcześniej korekty;
- zdarzenia przychodzące podczas odświeżenia nie są gubione;
- nowsza generacja decyzji zatrzymuje pozostałe stare cele grupy rolet;
- retry respektuje finalny cel BehavioralLearner i nie blokuje alarmów
  deszczu/wiatru limitami komfortowymi;
- niedostępna encja końca przechodzi na godzinę jawną, a następnie zachód;
- reset ręcznego przejęcia wymaga potwierdzonej pozycji napędu;
- niestandardowy czas ręcznego przejęcia jest spójny między formularzem i
  encją select.
- koniec zwykłego harmonogramu jest decyzją `timed_end`, przechodzi przez
  arbiter i zachowuje fizyczne limity pozycji.

### Architektura

- `coordinator.py` został zmniejszony do 190 linii;
- wydzielono także etapowy `coordinator_pipeline.py`, moduły zdarzeń, danych,
  wykonania, ruchów, harmonogramu, opcji, ręcznego sterowania, geometrii i
  klimatu;
- reguły korzystają z jednego snapshota i jawnego arbitra priorytetów;
- usługi domeny `cover` są wywoływane wyłącznie w `movement.py`;
- usunięto stary monolityczny `calculation.py`;
- diagnostyka zawiera generacje zdarzeń, pełny ślad decyzji, finalne cele i
  źródła harmonogramu;
- 110 testów obejmuje testy jednostkowe oraz rzeczywisty cykl życia na Home
  Assistant 2026.7.4.

### Aktualizacja

Wydanie zachowuje domenę `adaptive_cover` i istniejące wpisy konfiguracji.
Wymaga Home Assistant `2026.7+` i Python `3.14.2+`.
Wymagany jest pełny restart Home Assistant po aktualizacji. Zalecane jest
pierwsze uruchomienie z aktywnym trybem Dry Run oraz eksport diagnostyki z
`refresh: true`.

## English

Version 1.6.0 completes the stabilization and modularization plan. Timers,
sensor events, manual control and retries now use one decision path and one
physical cover-command gateway.

### Behavior fixes

- the night-purge deadline selects an explicit night position while preserving
  rain, wind, cold and open-window safety;
- cold protection uses a `1°C` hysteresis to prevent nighttime switching around
  the configured threshold;
- intermediate and duplicate reports from the integration's own movement no
  longer trigger manual override or BehavioralLearner;
- older learning offsets potentially created from those reports are reset once
  without removing the last direct-sun timestamp;
- low radiation with zero thermal stress restores the default position despite
  a high temperature forecast;
- an unavailable configured indoor-temperature sensor is not replaced with the
  outdoor reading, preventing false thermal stress and near-total closing;
- the Astral sunset timestamp is converted from UTC to the Home Assistant local
  timezone before night purge can start;
- short outdoor-sensor jumps greater than `3°C` are rejected until the new
  value persists for five minutes;
- night mode uses the configured sunset position instead of briefly restoring
  the daytime `100%` target before purge starts;
- BehavioralLearner ignores movement outside the active schedule, and the
  version `4` guard migration removes previously created offsets;
- refresh events arriving during an update are retained;
- a newer decision generation stops remaining stale group targets;
- retries use the final BehavioralLearner target and emergency rain/wind
  retries bypass comfort movement limits;
- an unavailable end entity falls back to explicit time and then sunset;
- manual-override reset requires a confirmed physical target;
- custom override durations stay consistent between the form and select
  entity.
- normal schedule completion is an explicit `timed_end` decision that passes
  through the arbiter and retains physical position limits.

### Architecture

- `coordinator.py` is reduced to 190 lines;
- the staged `coordinator_pipeline.py`, events, data preparation, execution,
  movement, schedule, options, manual control, geometry and climate have
  separate modules;
- rules use one input snapshot and an explicit priority arbiter;
- only `movement.py` calls services in the `cover` domain;
- the former monolithic `calculation.py` has been removed;
- diagnostics expose refresh generations, the full decision trace, final
  targets and schedule resolution;
- 110 tests include unit coverage and a real Home Assistant 2026.7.4 lifecycle.

The release keeps the `adaptive_cover` domain and existing config entries.
It requires Home Assistant `2026.7+` and Python `3.14.2+`.
Perform a full Home Assistant restart after upgrading. A first run in Dry Run
mode followed by a diagnostics export with `refresh: true` is recommended.
