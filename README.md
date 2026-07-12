# 오늘의신기템

쿠팡 파트너스 상품 링크 허브. https://todaysingi.netlify.app

## 상품 추가

    python scripts/add_product.py --title "제목" --price 12900 \
        --image "https://...jpg" --link "https://link.coupang.com/a/xxxx" --push

push하면 Netlify가 약 1분 내 자동 배포한다.

## 구조

정적 사이트(index.html + app.js)가 products.json을 읽는다. 빌드 없음.
- 상품 숨기기: 해당 항목 `"active": false` 후 push
- GA4 연결: app.js 상단 `GA_MEASUREMENT_ID`에 측정 ID 입력
- 설계 문서: docs/superpowers/specs/
