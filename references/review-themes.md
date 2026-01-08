# Review-driven refactor themes (project-agnostic)

특정 코드베이스가 달라도, 실제 코드리뷰에서 반복적으로 “수정까지 이어지는” 패턴은 유사합니다. 아래 테마는 프로젝트에 종속되지 않도록 일반화한 앵커입니다.

## 1) Dependency direction fixes (DIP)
- **역방향 의존 제거**: low-level(인프라/클라이언트/데이터 접근)이 high-level(정책/유즈케이스/서비스)에 의존하면, 변경 비용이 폭발한다.
- **경계 타입 좁히기**: 어댑터는 “payload 전송”만 알고, 서비스 결과 객체를 직접 알지 않게 만든다(= leaky abstraction 방지).

## 2) DI / Composition root 정리
- `create()`/entrypoint에서만 I/O + 의존성 wiring.
- 코어 로직은 입력을 받고 결정을 내리는 순수 함수/객체로 유지.
- 시간/랜덤/클라이언트/설정 로더는 주입 가능하게 만들어 테스트를 안정화.

## 3) Typing 강화 + raw dict 전파 차단
- 경계에서 `TypedDict`/Pydantic으로 “shape”를 고정하고 내부로 전달.
- mypy가 잡아줄 수 있도록 `None`/optional을 명시적으로 다룬다.
- 불필요한 래퍼/프로퍼티는 제거하고 표준 API를 직접 사용(유지보수 비용 절감).

## 4) Config modeling + invariant validation
- 설정이 “데이터”인 경우, 하드코딩 분기 대신 data-driven 조건 리스트로 확장 가능하게 설계.
- `model_validator`로 정렬/연속성/필수 필드/범위 같은 invariant를 로드 시점에 검증.

## 5) Copy-paste artifact 제거
- 클래스명/파일명/docstring이 실제 역할과 불일치하면, 이후 변경 시 오해를 유발한다.
- “이름/설명 정합성”은 단순 스타일이 아니라 유지보수성 문제로 다룬다.

## 6) Quality gate 통과를 위한 마무리
- flake8/mypy에서 반복적으로 지적되는 유형(unused, 타입 불일치, `None` 누락)은 PR 단계에서 선제적으로 제거.
- 테스트도 구조 변경에 맞춰 “행동 중심”으로 정리해 회귀 위험을 줄인다.

