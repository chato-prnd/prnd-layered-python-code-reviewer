# Layered Python code review principles (재발 방지용)

이 체크리스트는 특정 프로젝트에 종속되지 않도록, 다양한 팀/프로젝트에서 반복되는 리뷰 포인트를 “근거(원칙) + 수정 제안(패턴)” 형태로 정리한 것입니다.

## 1) Architecture / Layering

### 원칙
- `domain/`(또는 이에 준하는 레이어)은 **순수 도메인 모델**(entities/value objects)로 유지한다.
- `dataset/`/`repository/`는 **data access + shaping** 역할만 가진다(raw row → domain 변환).
- `adapters/`/`clients/`는 **외부 시스템 통신**만 담당하고, 내부 서비스/정책 타입에 의존하지 않는다.
- `service/`/`usecases/`는 **애플리케이션 오케스트레이션**(workflow)이며, 정책/룰 평가 및 결과 통합을 담당한다.

### 금지(리뷰에서 blocker)
- low-level 레이어(예: `adapters/`, `dataset/`, `infra/`)가 high-level 레이어(예: `service/`, `usecases/`, `policy/`) 타입을 import 하는 경우
  - 용어: **DIP violation**, **reversed dependency**, **leaky abstraction**
  - 수정 패턴: 서비스 타입 의존을 제거하고, **어댑터 전용 payload 모델** 또는 **domain 모델**로 경계를 좁힌다.

## 2) DI / DIP / Composition root

### 원칙
- **constructor injection**: 클래스는 의존성을 내부에서 생성하지 말고 주입받는다.
- **composition root**: I/O(설정 로드, 파일/네트워크 접근, HTTP client 생성)는 `create()`/entrypoint 등 경계에서만 수행한다.
- 코어 로직(룰/오케스트레이션)은 “입력→결정→출력”에 집중하고, 외부환경을 몰라야 한다.

### 리뷰 질문
- “이 클래스는 자신이 쓰는 의존성을 직접 new 하고 있나?”
- “로직이 설정 파일 경로/HTTP/ENV 등 외부 환경을 직접 다루나?”
- “테스트에서 교체 가능한 seam(시간/설정/클라이언트)이 존재하나?”

## 3) Schema / Typing / Data shaping

### 원칙
- Raw dict를 흘려보내지 말고, 경계에서 `TypedDict`/Pydantic으로 **명시적 타입**을 부여한다.
- 함수 반환은 가능하면 `dict` 대신 `TypedDict` / Pydantic model을 사용한다.
- Magic string은 `Enum` 또는 `Literal`을 사용한다(예: 상태/타입/전략 식별자).

### 리뷰 코멘트 템플릿
- “여기는 `dict`가 레이어를 넘어 전파됩니다. 경계에서 `TypedDict`로 shape를 고정하고, 내부에는 `domain`의 명시적 모델로 변환해 전달하는 편이 안전합니다.”

## 4) Config modeling / Validation

### 원칙
- YAML/ENV 기반 설정은 Pydantic 모델로 파싱하고, `model_validator`로 **invariant**를 검증한다.
  - 예: 가격 구간 조건의 정렬/연속성, 필수 키 존재, 값 범위(ge/gt/lt).
- 하드코딩 분기(`if price < 2000`) 대신 **data-driven 조건 리스트**로 확장 가능하게 만든다.

### 리뷰 코멘트 템플릿
- “이 분기 조건은 매직 넘버/정책 하드코딩으로 보입니다. `configs.py`의 조건 모델처럼 data-driven으로 옮겨두면 정책 변경 시 코드 수정 범위를 줄일 수 있습니다.”

## 5) Error handling at boundaries

### 원칙
- 외부 통신(adaptor)에서는 예외를 적절히 처리하되, 코어 로직에는 broad `except`를 두지 않는다.
- 실패를 무시해야 하는 경우(예: 알림)는 **swallow-on-failure**로 처리하되, 로그에 context를 남긴다.

### 리뷰 포인트
- `except Exception`이 있는 위치가 “경계(adaptor)”인지 확인한다.
- 로그 메시지에 `car_id`, 요청 URL 등 **디버깅 키**가 포함되는지 확인한다.

## 6) Naming / Docs (copy-paste artifact 방지)

### 원칙
- 클래스명/파일명/docstring은 실제 역할과 일치해야 한다(복붙 흔적 금지).
- `Settings` vs `Configs`는 용어를 엄격히 구분한다.
  - `Settings`: 환경/런타임(ENV, endpoint, token)
  - `Configs`: 룰/정책 파라미터(YAML로 제공되는 business rule inputs)

### 리뷰 코멘트 템플릿
- “Docstring/클래스명이 다른 로직명을 가리키고 있어 copy-paste artifact로 보입니다. 이후 유지보수 비용을 줄이기 위해 이름/설명을 정합하게 맞추는 것이 좋습니다.”

## 7) Tests / Determinism

### 원칙
- 시간 의존 로직은 `target_date`/provider를 통해 테스트에서 고정 가능해야 한다.
- 테스트는 구조(구현 세부)보다 **행동(결정 규칙)**을 검증한다.
- 주요 edge case를 명시적으로 포함한다:
  - 예측치 없음/실패, 쿨다운 미충족, 최대 인하폭 제한, price_cut=0인 경우

## 8) Quality gate

### 필수
- 변경 후 `flake8` 및 `mypy`(또는 동급의 lint/type checker)를 통과한다. (Poetry 사용 시: `poetry run flake8 . && poetry run mypy .`)
- unused 변수/타입 불일치/`None` 누락 처리는 “리뷰에서 발견되기 전에” 해결한다.
