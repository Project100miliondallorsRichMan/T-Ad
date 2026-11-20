# 테스트용 합성 사진

`photos/`의 4장은 **코드로 그린 합성 이미지**입니다. 실제 티링크 현장 사진이 아니므로 발표·홍보물에 실제 사례처럼 쓰지 않습니다.
글자, 번호, IP 같은 정보는 넣지 않았습니다.

| 파일 | 장면 | 기대하는 분석 결과 |
|---|---|---|
| `1_before_cabinet.jpg` | 패치패널과 케이블로 꽉 찬 단자함 | 문제 태그: 단자함 공간 부족 / 배선 정리 필요 |
| `2_after_wall_server.jpg` | 벽 선반 위 녹취서버, 아래 단자함으로 배선 | 벽에 따로 설치한 장비 |
| `3_mirroring_switch.jpg` | 8포트 소형 스위치 클로즈업 | 설치 형태: 미러링 스위치허브 |
| `4_existing_phone.jpg` | 책상 위 인터넷 전화기 | 기존 전화기 유지 |

다시 만들기: `python sample_data/make_photos.py sample_data/photos`
