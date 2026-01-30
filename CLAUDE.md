# 경인블루저널 보도자료 자동화 프로세스

## 개요
- **목적**: 보도자료를 경인블루저널(bluejournal.co.kr)에 업로드
- **현재 범위**: 수원시, 경기도, **용인시**, **화성시**, **성남시**, **고양시**, **인천시**, **부천시**, **안산시**
- **수집 방식**:
  - Daum 메일 수신 (수원시, 경기도)
  - **시군 홈페이지 직접 수집** (용인시, 화성시, 성남시, 고양시, 인천시, 부천시, 안산시)
- **향후 확장**: 경기도 전체 시군

### ⚠️ 핵심 규칙
1. **🖼️ 사진 있는 보도자료만 기사로 등록** - 사진이 없는 보도자료는 업로드하지 않음
2. **📝 기사 + 사진 필수** - 제목, 본문 내용, 대표이미지 업로드 + 본문에 이미지 삽입 모두 필수
3. **기자명은 "경인블루저널"** - 모든 기사의 작성자는 고정
4. **섹션 설정** - 1차: 지역뉴스(40), 2차: 경기(4020) 또는 인천(4010), 출력위치: 중앙섹션

---

## 1. 시스템 구성

### 1.1 계정 정보 (.env 파일에서 관리)

**⚠️ 중요: 실제 비밀번호는 절대 이 파일에 작성하지 마세요!**

```python
# config.py - 환경변수에서 로드
import os
from dotenv import load_dotenv
load_dotenv()

# Daum/Kakao 메일
DAUM_EMAIL = os.getenv("DAUM_EMAIL")
DAUM_PASSWORD = os.getenv("DAUM_PASSWORD")

# NetPro CMS (경인블루저널)
NETPRO_LOGIN_URL = "http://bluejournal.co.kr/bbs/login.php"
NETPRO_ADMIN_ID = os.getenv("NETPRO_ADMIN_ID")
NETPRO_ADMIN_PW = os.getenv("NETPRO_ADMIN_PW")
NETPRO_NEWS_WRITE_URL = "http://bluejournal.co.kr/adm/write.php?bo_table=news"
```

**.env 파일 예시** (이 파일은 .gitignore에 포함됨):
```
DAUM_EMAIL=your_email@kakao.com
DAUM_PASSWORD=your_password
NETPRO_ADMIN_ID=admin
NETPRO_ADMIN_PW=your_password
```

### 1.2 필요 도구
- Python 3.x
- Playwright (브라우저 자동화)
- HWP Reader (한글 파일 텍스트 추출)

---

## 2. 시군 홈페이지 보도자료 수집 (용인시, 화성시)

### 2.0 용인시 보도자료 수집

#### 보도자료 URL
```
https://www.yongin.go.kr/user/bbs/BD_selectBbsList.do?q_bbsCode=1020
```

#### 수집 절차
1. **보도자료 목록 확인**
   - 오늘 날짜 보도자료 중 **사진 첨부된 것만** 선별
   - 기사 제목과 URL 수집

2. **이미지 다운로드**
   - 첨부파일 URL 패턴: `https://www.yongin.go.kr/component/file/ND_fileDownload.do?q_fileSn=XXX&q_fileId=XXX`
   - Python requests SSL 오류 시 **curl -k** 사용
   ```bash
   curl -k -o "filename.jpg" "다운로드URL" -A "Mozilla/5.0"
   ```
   - 다운로드 경로: `downloads/YYYYMMDD_yongin/`

3. **본문 내용 추출**
   - 각 기사 상세 페이지에서 본문 텍스트 추출
   - JavaScript로 body.innerText에서 "- " 시작점 찾아 추출
   - "본 저작물" 또는 "담당부서" 앞에서 자르기

4. **기사 등록** (기사 + 사진 필수)
   - 제목 입력
   - 대표이미지 업로드
   - 본문에 이미지 삽입 + 원문 내용 추가
   - 저장

### 2.1 화성시 보도자료 수집

#### 보도자료 URL
```
https://www.hscity.go.kr/user/bbs/BD_selectBbsList.do?q_bbsCode=1043
```

#### 수집 절차
1. **보도자료 확인**
   - HWP 파일 + 사진 ZIP 파일 다운로드
   - 다운로드 경로: `downloads/YYYYMMDD_hwaseong/`

2. **ZIP 압축 해제**
   ```powershell
   Expand-Archive -Path "photo_1.zip" -DestinationPath "photo_1" -Force
   ```

3. **HWP 텍스트 추출**
   - `olefile` 라이브러리 사용
   - PrvText 스트림에서 UTF-16 디코딩
   - 인코딩 오류 시 홈페이지에서 제목 직접 수집

4. **기사-이미지 매핑**
   - 파일명 번호로 매핑: `1-1.jpg` → 1번 기사
   - 폴더별 구분: `photo_1/` → 1번 기사

### 2.2 성남시 보도자료 수집

#### 보도자료 URL
```
https://www.seongnam.go.kr/city/1000060/30005/bbsList.do
```

#### 기사 상세 URL 패턴
```
https://www.seongnam.go.kr/city/1000060/30005/bbsView.do?idx={기사번호}
```

#### 수집 절차
1. **보도자료 목록 확인**
   - 오늘 날짜 기사 중 **사진 첨부된 것만** 선별
   - 테이블에서 제목 클릭하여 상세 페이지 이동

2. **첨부파일 확인**
   - 이미지 파일(.jpg, .png) 첨부 여부 확인
   - **이미지 없으면 업로드 스킵**

3. **본문 및 이미지 추출**
   - 상세 페이지에서 본문 텍스트 추출
   - 첨부 이미지 다운로드

### 2.3 고양시 보도자료 수집

#### 보도자료 URL
```
https://www.goyang.go.kr/news/user/bbs/BD_selectBbsList.do?q_bbsCode=1090&q_estnColumn1=All
```

#### 이미지 다운로드 URL 패턴
```
https://www.goyang.go.kr/component/file/ND_fileDownload.do?q_fileSn={파일번호}&q_fileId={파일ID}
```

#### 수집 절차
1. **보도자료 목록 확인**
   - 오늘 날짜 기사 중 파일 아이콘 있는 것 확인
   - **이미지 첨부된 기사만** 선별

2. **첨부파일 확인**
   - HWP만 있는 기사는 **스킵**
   - 이미지 파일(.jpg, .png) 있는 기사만 처리

3. **다운로드**
   - curl -k로 이미지 다운로드
   - 다운로드 경로: `downloads/YYYYMMDD_goyang/`

### 2.4 인천시 보도자료 수집

#### 보도자료 URL
```
https://www.incheon.go.kr/IC010205
```

#### 기사 상세 URL 패턴
```
https://www.incheon.go.kr/IC010205/view?repSeq={기사ID}&curPage=1
```

#### 이미지 다운로드 URL 패턴
```
https://www.incheon.go.kr/comm/dmsFileDownload?attachFileSeq={파일ID}&attachFileDetailSeq=0
```

#### 수집 절차
1. **보도자료 목록 확인**
   - 오늘 날짜 기사 중 **이미지 첨부된 것만** 선별
   - 목록에서 "이미지 없음" 표시된 기사는 스킵
   - 기사 제목 클릭하여 상세 페이지 이동

2. **첨부파일 확인**
   - 상세 페이지에서 "이미지파일" 항목 확인
   - `.jpg`, `.png` 이미지 파일 있는지 확인
   - **이미지 없으면 업로드 스킵**

3. **본문 및 이미지 추출**
   - 상세 페이지에서 본문 텍스트 추출 (body.innerText)
   - "인천광역시(시장" 시작점부터 "이미지파일" 앞까지 추출
   - 다운로드 링크에서 이미지 URL 추출

4. **다운로드**
   - curl -k로 이미지 다운로드
   - 다운로드 경로: `downloads/YYYYMMDD_incheon/`

5. **기사 등록**
   - 1차 섹션: 지역뉴스(40)
   - **2차 섹션: 인천(4010)** ← 경기도와 다름
   - 기자명: 경인블루저널
   - 제목, 본문, 이미지 업로드

### 2.5 부천시 보도자료 수집

#### 보도자료 URL
```
https://bucheon.go.kr/site/program/board/basicboard/list?boardtypeid=26748&menuid=148002002001
```

#### 첨부파일 다운로드 URL 패턴
```
https://bucheon.go.kr/site/inc/file/fileDownload?dirname=/board/1187&filename={파일명}
```

#### 수집 방식
부천시는 **날짜별로 보도자료를 묶어서** 게시 (예: "부천시 1월 29일 보도자료입니다")
- HWP 파일: 기획 보도자료, 정기 보도자료
- ZIP 파일: 기획 사진자료, 정기 사진자료

#### 수집 절차
1. **보도자료 목록 확인**
   - 오늘 날짜 보도자료 클릭 (예: "부천시 1월 29일 보도자료입니다")
   - 상세 페이지에서 첨부파일 목록 확인

2. **첨부파일 다운로드**
   - 사진자료 ZIP 파일 다운로드 (기획 사진자료.zip, 정기 사진자료.zip)
   - 다운로드 경로: `downloads/YYYYMMDD_bucheon/`

3. **ZIP 압축 해제**
   ```powershell
   Expand-Archive -Path "기획 사진자료.zip" -DestinationPath "기획" -Force
   Expand-Archive -Path "정기 사진자료.zip" -DestinationPath "정기" -Force
   ```

4. **기사-이미지 매핑**
   - 파일명 번호로 매핑: `1-1.jpg`, `1-2.jpg` → 1번 기사
   - 보도자료 목차와 이미지 번호 매칭

5. **기사 등록**
   - 1차 섹션: 지역뉴스(40)
   - 2차 섹션: 경기(4020)
   - 기자명: 경인블루저널
   - 제목, 본문, 이미지 업로드

### 2.6 안산시 보도자료 수집

#### 보도자료 URL
```
https://www.ansan.go.kr/www/common/bbs/selectPageListBbs.do?bbs_code=B0238
```

#### 이미지 URL 패턴
```
https://www.ansan.go.kr/cmsdata/web_upload/bbs/B0238/{날짜}/{파일ID}.jpg
```

#### 수집 절차
1. **보도자료 목록 확인**
   - 오늘 날짜 기사 중 **jpg 파일 첨부된 것만** 선별
   - 첨부파일 열에 "jpg 파일" 표시 확인
   - 기사 제목 클릭하여 상세 페이지 이동

2. **이미지 추출**
   - 상세 페이지 내 `<img>` 태그에서 이미지 URL 추출
   - URL 패턴: `cmsdata/web_upload/bbs/B0238/...`

3. **본문 추출**
   - 상세 페이지에서 본문 텍스트 추출
   - "안산시(시장" 시작점부터 "담당부서" 앞까지 추출

4. **다운로드**
   - curl -k로 이미지 다운로드
   - 다운로드 경로: `downloads/YYYYMMDD_ansan/`

5. **기사 등록**
   - 1차 섹션: 지역뉴스(40)
   - 2차 섹션: 경기(4020)
   - 기자명: 경인블루저널
   - 제목, 본문, 이미지 업로드

---

## 3. 프로세스 단계 (Daum 메일 - 수원시, 경기도)

### 3.1 Step 1: Daum 메일 로그인
1. https://mail.daum.net 접속
2. "카카오로 로그인" 클릭
3. 이메일/비밀번호 입력 후 로그인

**주의사항**:
- 로그인 후 `networkidle` 상태까지 대기 필요
- 2FA가 활성화된 경우 추가 처리 필요

### 3.2 Step 2: 보도자료 메일 확인
1. 받은메일함에서 보도자료 메일 검색
2. 메일 제목 패턴: `[YYYYMMDD 수원시 보도자료]제목 등 N건`
3. 메일 클릭하여 열기

**보도자료 메일 식별 패턴**:
```
수원시언론담당관 → 수원시 보도자료
경기도청 대변인 → 경기도 보도자료
```

### 3.3 Step 3: 첨부파일 다운로드

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

### 3.4 Step 4: HWP 텍스트 추출
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

### 3.5 Step 5: NetPro CMS 로그인
1. http://bluejournal.co.kr/bbs/login.php 접속
2. 아이디/비밀번호 입력
3. 로그인 버튼 클릭 (또는 Enter)

**로그인 폼 셀렉터**:
```python
page.fill('input[name="mb_id"]', NETPRO_ADMIN_ID)
page.fill('input[name="mb_password"]', NETPRO_ADMIN_PW)
```

### 3.6 Step 6: 기사 등록

#### 6.1 뉴스등록 페이지 이동
```
http://bluejournal.co.kr/adm/write.php?bo_table=news
```

#### 6.2 필수 입력 항목
| 항목 | 셀렉터 | 값 |
|------|--------|-----|
| **기자명** | `input[name="wr_name"]` | **"경인블루저널"** (필수) |
| 출력위치 | checkbox (중앙섹션) | 체크 |
| 1차 뉴스 섹션 | select | "지역뉴스" |
| 2차 섹션 | select | "경기" |
| 제목 | `input[name="wr_subject"]` | 기사 제목 |
| 본문 | CKEditor iframe | 기사 내용 |
| 대표이미지 | `input[name="wr_image"]` | 이미지 파일 |

**⚠️ 중요: 모든 기사의 기자명(작성자)은 반드시 "경인블루저널"로 설정해야 함**

```javascript
// 기자명 설정
document.querySelector('input[name="wr_name"]').value = '경인블루저널';
```

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
    "수원시": ("지역뉴스", "경기"),      # 40, 4020
    "성남시": ("지역뉴스", "경기"),      # 40, 4020
    "고양시": ("지역뉴스", "경기"),      # 40, 4020
    "용인시": ("지역뉴스", "경기"),      # 40, 4020
    "화성시": ("지역뉴스", "경기"),      # 40, 4020
    "인천시": ("지역뉴스", "인천"),      # 40, 4010 ← 인천은 별도 코드
    "부천시": ("지역뉴스", "경기"),      # 40, 4020
    "안산시": ("지역뉴스", "경기"),      # 40, 4020
    # ... 모든 시군
    "경기도": ("지역뉴스", "경기"),      # 40, 4020
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
- [ ] **대표이미지 업로드 (필수!)**
- [ ] **본문에 이미지 삽입 (필수!)**
- [ ] 저장

### 업로드 후
- [ ] 기사 목록에서 등록 확인
- [ ] 실제 사이트에서 표시 확인

---

## 9. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-01-30 | **안산시 보도자료 수집 방식 추가** - 보도자료 목록에서 jpg 첨부 확인, cmsdata 이미지 URL 추출, 2건 업로드 완료 |
| 2026-01-30 | **부천시 보도자료 수집 방식 추가** - 날짜별 묶음 게시 방식, HWP+ZIP 다운로드, 3건 업로드 완료 |
| 2026-01-30 | **인천시 보도자료 수집 방식 추가** - 인천시 홈페이지 URL, 2차섹션 인천(4010) 설정, 3건 업로드 완료 |
| 2026-01-30 | **성남시, 고양시 보도자료 수집 방식 추가** - 시군 홈페이지 URL 및 수집 절차 문서화 |
| 2026-01-30 | **용인시, 화성시 보도자료 수집 방식 추가** - 시군 홈페이지 직접 수집, curl 다운로드, 본문 추출 방법 |
| 2026-01-30 | **기사+사진 필수 규칙 강화** - 사진 있는 보도자료만 업로드, 제목+본문+이미지 모두 필수 |
| 2026-01-30 | 화성시 8건, 용인시 7건 기사 업로드 완료 |
| 2026-01-29 | 기자명(작성자) "경인블루저널" 고정 설정 추가 |
| 2026-01-29 | 본문 이미지 삽입 방법 추가, 기자선택/출력위치 처리 방법 추가 |
| 2026-01-29 | 최초 작성 - 수원시 보도자료 3건 업로드 완료 |
