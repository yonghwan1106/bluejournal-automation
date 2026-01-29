# 경인블루저널 보도자료 자동화 프로세스

## 개요
- **목적**: Daum 메일로 수신된 보도자료를 경인블루저널(bluejournal.co.kr)에 자동 업로드
- **현재 범위**: 수원시, 경기도
- **향후 확장**: 경기도 전체 시군

---

## 1. 시스템 구성

### 1.1 계정 정보 (config.py)
```python
# Daum/Kakao 메일
DAUM_EMAIL = "bluejournal@kakao.com"
DAUM_PASSWORD = "Tsano3382!"

# NetPro CMS (경인블루저널)
NETPRO_LOGIN_URL = "http://bluejournal.co.kr/bbs/login.php"
NETPRO_ADMIN_ID = "admin"
NETPRO_ADMIN_PW = "sano3382"
NETPRO_NEWS_WRITE_URL = "http://bluejournal.co.kr/adm/write.php?bo_table=news"
```

### 1.2 필요 도구
- Python 3.x
- Playwright (브라우저 자동화)
- HWP Reader (한글 파일 텍스트 추출)

---

## 2. 프로세스 단계

### 2.1 Step 1: Daum 메일 로그인
1. https://mail.daum.net 접속
2. "카카오로 로그인" 클릭
3. 이메일/비밀번호 입력 후 로그인

**주의사항**:
- 로그인 후 `networkidle` 상태까지 대기 필요
- 2FA가 활성화된 경우 추가 처리 필요

### 2.2 Step 2: 보도자료 메일 확인
1. 받은메일함에서 보도자료 메일 검색
2. 메일 제목 패턴: `[YYYYMMDD 수원시 보도자료]제목 등 N건`
3. 메일 클릭하여 열기

**보도자료 메일 식별 패턴**:
```
수원시언론담당관 → 수원시 보도자료
경기도청 대변인 → 경기도 보도자료
```

### 2.3 Step 3: 첨부파일 다운로드

#### 3.1 첨부파일 목록 확인
- "목록으로 보기" 클릭하여 파일 목록 표시
- 파일 유형:
  - `.hwp` / `.hwpx`: 보도자료 본문
  - `.jpg` / `.png`: 사진 자료

#### 3.2 HWP 파일 다운로드
- 파일명 왼쪽의 다운로드 아이콘(↓) 클릭
- 또는 파일명 클릭 후 다운로드 버튼 클릭

#### 3.3 이미지 파일 다운로드
- 각 이미지 파일의 다운로드 아이콘 클릭
- 파일명 패턴: `N. 제목.jpg` (N은 기사 번호)
- **매핑 규칙**:
  ```
  1-1, 1-2 → 첫 번째 기사 이미지
  2 → 두 번째 기사 이미지
  3 → 세 번째 기사 이미지
  ```

**다운로드 경로**:
```
C:\Users\user\projects\2026_active\bluejournal-automation\suwon_images\
```

### 2.4 Step 4: HWP 텍스트 추출
```python
# hwp_reader.py 사용
from hwp_reader import extract_text
text = extract_text("보도자료.hwp")
```

**보도자료 구조**:
```
보도자료 1.
제목
부제목
본문...

보도자료 2.
제목
...
```

### 2.5 Step 5: NetPro CMS 로그인
1. http://bluejournal.co.kr/bbs/login.php 접속
2. 아이디/비밀번호 입력
3. 로그인 버튼 클릭 (또는 Enter)

**로그인 폼 셀렉터**:
```python
page.fill('input[name="mb_id"]', NETPRO_ADMIN_ID)
page.fill('input[name="mb_password"]', NETPRO_ADMIN_PW)
```

### 2.6 Step 6: 기사 등록

#### 6.1 뉴스등록 페이지 이동
```
http://bluejournal.co.kr/adm/write.php?bo_table=news
```

#### 6.2 필수 입력 항목
| 항목 | 셀렉터 | 값 |
|------|--------|-----|
| 출력위치 | checkbox (중앙섹션) | 체크 |
| 1차 뉴스 섹션 | select | "지역뉴스" |
| 2차 섹션 | select | "경기" |
| 제목 | `input[name="wr_subject"]` | 기사 제목 |
| 본문 | CKEditor iframe | 기사 내용 |
| 대표이미지 | `input[name="wr_image"]` | 이미지 파일 |

#### 6.3 본문 입력 (CKEditor)
```python
# iframe 내부에 입력
page.frame_locator('iframe.cheditor-editarea').locator('body').fill(content)
```

#### 6.4 대표이미지 업로드
```python
page.locator('input[name="wr_image"]').set_input_files(image_path)
```

#### 6.5 본문에 이미지 삽입 (중요!)
대표이미지만 업로드하면 기사 본문에는 이미지가 표시되지 않음.
본문에 이미지를 표시하려면 `<img>` 태그를 직접 삽입해야 함.

```javascript
// 관리자 수정 페이지에서 실행
(function() {
  // 대표이미지 URL 찾기
  const imagePreview = document.querySelector('img[src*="data/file/news"]');
  const imageUrl = imagePreview?.src;
  const title = document.querySelector('input[name="wr_subject"]')?.value;

  if (!imageUrl) return { error: '이미지 없음' };

  // img 태그 생성
  const imgTag = '<p style="text-align:center;"><img src="' + imageUrl + '" alt="' + (title || '') + '" style="max-width:100%;"></p>\n';

  // textarea에 삽입 (필수)
  const wrContent = document.querySelector('textarea[name="wr_content"]');
  if (wrContent && !wrContent.value.includes('<img')) {
    wrContent.value = imgTag + wrContent.value;
  }

  // cheditor iframe에도 삽입 (필수)
  const iframe = document.querySelector('iframe.cheditor-editarea');
  if (iframe?.contentDocument?.body && !iframe.contentDocument.body.innerHTML.includes('<img')) {
    iframe.contentDocument.body.innerHTML = imgTag + iframe.contentDocument.body.innerHTML;
  }

  return { success: true, imageUrl: imageUrl };
})()
```

**주의사항**:
- `textarea[name="wr_content"]`와 `iframe.cheditor-editarea` 양쪽 모두에 삽입해야 저장 시 반영됨
- 이미 이미지가 있는 경우 중복 삽입 방지 필요 (`includes('<img')` 체크)

#### 6.6 기자 선택 팝업 처리
기사 저장 시 기자 선택 팝업이 나타남. JavaScript 함수로 처리:

```javascript
// 수원시 기사
sel_names('수원시','bluejournal@daum.net');

// 경기도 기사
sel_names('경기도','bluejournal@daum.net');
```

#### 6.7 출력위치 설정
기사가 특정 섹션에 표시되려면 출력위치 체크박스 선택 필요:

```javascript
// 중앙섹션 (메인 페이지 표시)
document.querySelector('input[name="wr_position[]"][value="main_center"]').checked = true;
```

#### 6.8 저장
```python
page.click('input[type="submit"].btn_01')
```

---

## 3. 기사-이미지 매핑 규칙

### 3.1 파일명 기반 매핑
```python
def match_image_to_article(image_filename, article_title):
    """
    이미지 파일명에서 기사 번호를 추출하여 매핑

    예시:
    - "1-1. 수원 금곡동에 공공도서관 건립된다.jpg" → 기사 1
    - "2. 수원페이 인센티브 20%로 확대.jpg" → 기사 2
    - "3. 푸른손길 입양쉼터 지정.jpg" → 기사 3
    """
    # 파일명에서 번호 추출
    match = re.match(r'^(\d+)[-.]', image_filename)
    if match:
        return int(match.group(1))
    return None
```

### 3.2 키워드 기반 매핑
```python
article_image_map = {
    "금곡동": ["금곡", "도서관"],
    "수원페이": ["수원페이", "인센티브"],
    "입양쉼터": ["입양", "푸른손길", "유기동물"],
}
```

---

## 4. 에러 처리

### 4.1 일반적인 오류
| 오류 | 원인 | 해결책 |
|------|------|--------|
| 로그인 실패 | 세션 만료, 비밀번호 변경 | 재로그인 시도 |
| 다운로드 타임아웃 | 네트워크 지연 | 재시도, 타임아웃 증가 |
| CKEditor 입력 실패 | iframe 로드 지연 | 대기 시간 추가 |
| 이미지 업로드 실패 | 파일 형식 문제 | PNG/JPG 확인 |

### 4.2 재시도 로직
```python
max_retries = 3
for attempt in range(max_retries):
    try:
        # 작업 수행
        break
    except Exception as e:
        if attempt < max_retries - 1:
            time.sleep(2)
            continue
        raise e
```

---

## 5. 확장 계획

### 5.1 경기도 시군 목록 (31개)
```python
GYEONGGI_CITIES = [
    "수원시", "성남시", "고양시", "용인시", "부천시",
    "안산시", "안양시", "남양주시", "화성시", "평택시",
    "의정부시", "시흥시", "파주시", "김포시", "광명시",
    "광주시", "군포시", "하남시", "오산시", "이천시",
    "안성시", "의왕시", "양평군", "여주시", "과천시",
    "구리시", "포천시", "양주시", "동두천시", "가평군", "연천군"
]
```

### 5.2 보도자료 메일 패턴
```python
PRESS_RELEASE_PATTERNS = [
    r"\[.*보도자료\]",
    r"보도자료.*송부",
    r"언론담당",
    r"대변인실",
]
```

### 5.3 섹션 매핑
```python
SECTION_MAP = {
    "수원시": ("지역뉴스", "경기"),
    "성남시": ("지역뉴스", "경기"),
    "고양시": ("지역뉴스", "경기"),
    # ... 모든 시군
    "경기도": ("지역뉴스", "경기"),
}
```

---

## 6. 파일 구조

```
bluejournal-automation/
├── config.py                 # 계정 정보, 설정
├── daum_mail_downloader.py   # 메일 다운로드 모듈
├── netpro_uploader.py        # CMS 업로드 모듈
├── hwp_reader.py             # HWP 텍스트 추출
├── main.py                   # 메인 실행 스크립트
├── PROCESS.md                # 이 문서
├── downloads/                # 다운로드된 HWP 파일
└── suwon_images/             # 다운로드된 이미지
```

---

## 7. 실행 방법

### 7.1 수동 실행
```bash
cd C:\Users\user\projects\2026_active\bluejournal-automation
python main.py
```

### 7.2 자동화 (예정)
- Windows Task Scheduler 사용
- 매일 오전 9시 실행
- 또는 메일 수신 시 트리거

---

## 8. 체크리스트

### 기사 업로드 전
- [ ] Daum 메일 로그인 확인
- [ ] 새 보도자료 메일 확인
- [ ] HWP 파일 다운로드
- [ ] 이미지 파일 다운로드
- [ ] HWP 텍스트 추출 및 파싱

### 기사 업로드
- [ ] NetPro 로그인
- [ ] 섹션 선택 (지역뉴스 > 경기)
- [ ] 제목 입력
- [ ] 본문 입력
- [ ] 대표이미지 업로드
- [ ] 저장

### 업로드 후
- [ ] 기사 목록에서 등록 확인
- [ ] 실제 사이트에서 표시 확인

---

## 9. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-01-29 | 본문 이미지 삽입 방법 추가, 기자선택/출력위치 처리 방법 추가 |
| 2026-01-29 | 최초 작성 - 수원시 보도자료 3건 업로드 완료 |
