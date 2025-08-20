.headers on
.mode column

.print '=== 테이블 목록 ==='
.tables

.print '\n=== Shop / Draw 스키마 ==='
PRAGMA table_info(Shop);
PRAGMA table_info(Draw);

.print '\n=== Draw 개수/최신 회차 ==='
SELECT COUNT(*) AS draws,
       MIN(round) AS min_round,
       MAX(round) AS max_round
FROM Draw;

.print '\n=== Shop 총개수와 rank 분포(상위) ==='
SELECT COUNT(*) AS shops FROM Shop;
SELECT rank, COUNT(*) AS cnt
FROM Shop
GROUP BY rank
ORDER BY cnt DESC
LIMIT 10;

.print '\n=== 최근 10회차의 "1등" 개수 (문자열 1등→숫자 캐스팅) ==='
SELECT round, COUNT(*) AS first_cnt
FROM Shop
WHERE CAST(REPLACE(REPLACE(rank, '등', ''), ' ', '') AS INTEGER) = 1
GROUP BY round
ORDER BY round DESC
LIMIT 10;

.print '\n=== 1등인데 좌표 없는 샵 (최대 30개) ==='
SELECT id, name, address, round, rank, lat, lng
FROM Shop
WHERE CAST(REPLACE(REPLACE(rank, '등', ''), ' ', '') AS INTEGER) = 1
  AND (lat IS NULL OR lng IS NULL OR lat = 0 OR lng = 0)
ORDER BY round DESC
LIMIT 30;

.print '\n=== Shop / Draw 회차 분포 비교 (상위 5개) ==='
SELECT 'Shop' AS src, round, COUNT(*) AS cnt FROM Shop GROUP BY round ORDER BY round DESC LIMIT 5;
SELECT 'Draw' AS src, round, COUNT(*) AS cnt FROM Draw GROUP BY round ORDER BY round DESC LIMIT 5;
