// 로또 웹 애플리케이션 JavaScript
class LottoApp {
    constructor() {
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.addAnimations();
        this.setupLottoBallColors();
        this.setupAutoRefresh();
    }

    setupEventListeners() {
        // 추천 번호 생성 버튼
        const generateBtn = document.getElementById('generate-recommendations');
        if (generateBtn) {
            generateBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.generateRecommendations();
            });
        }

        // 로또 볼 호버 효과
        document.querySelectorAll('.lotto-ball').forEach(ball => {
            ball.addEventListener('mouseenter', this.addBallHoverEffect.bind(this));
            ball.addEventListener('mouseleave', this.removeBallHoverEffect.bind(this));
        });

        // 카드 클릭 효과
        document.querySelectorAll('.card').forEach(card => {
            card.addEventListener('click', this.addCardClickEffect.bind(this));
        });

        // 스크롤 애니메이션
        this.setupScrollAnimations();
    }

    addAnimations() {
        // 페이지 로드 시 페이드인 애니메이션
        document.querySelectorAll('.card').forEach((card, index) => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';

            setTimeout(() => {
                card.style.transition = 'all 0.6s ease-out';
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }, index * 100);
        });
    }

    setupLottoBallColors() {
        // 로또 볼에 번호별 색상 클래스 추가
        document.querySelectorAll('.lotto-ball').forEach(ball => {
            const number = parseInt(ball.textContent);
            if (number >= 1 && number <= 10) {
                ball.classList.add('num-1-10');
            } else if (number >= 11 && number <= 20) {
                ball.classList.add('num-11-20');
            } else if (number >= 21 && number <= 30) {
                ball.classList.add('num-21-30');
            } else if (number >= 31 && number <= 40) {
                ball.classList.add('num-31-40');
            } else if (number >= 41 && number <= 45) {
                ball.classList.add('num-41-45');
            }
        });
    }

    addBallHoverEffect(event) {
        const ball = event.target;
        ball.style.transform = 'scale(1.2) rotate(5deg)';
        ball.style.boxShadow = '0 6px 12px rgba(0, 0, 0, 0.3)';

        // 주변 볼들도 약간 확대
        const nearbyBalls = this.getNearbyBalls(ball);
        nearbyBalls.forEach(nearbyBall => {
            nearbyBall.style.transform = 'scale(1.05)';
        });
    }

    removeBallHoverEffect(event) {
        const ball = event.target;
        ball.style.transform = '';
        ball.style.boxShadow = '';

        // 주변 볼들 원래대로
        const nearbyBalls = this.getNearbyBalls(ball);
        nearbyBalls.forEach(nearbyBall => {
            nearbyBall.style.transform = '';
        });
    }

    getNearbyBalls(ball) {
        const balls = Array.from(document.querySelectorAll('.lotto-ball'));
        const ballIndex = balls.indexOf(ball);
        const nearby = [];

        for (let i = Math.max(0, ballIndex - 2); i <= Math.min(balls.length - 1, ballIndex + 2); i++) {
            if (i !== ballIndex) {
                nearby.push(balls[i]);
            }
        }

        return nearby;
    }

    addCardClickEffect(event) {
        const card = event.currentTarget;
        card.style.transform = 'scale(0.98)';

        setTimeout(() => {
            card.style.transform = '';
        }, 150);
    }

    setupScrollAnimations() {
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('fade-in-up');
                }
            });
        }, observerOptions);

        document.querySelectorAll('.card, .stats-card').forEach(el => {
            observer.observe(el);
        });
    }

    async generateRecommendations() {
        const btn = document.getElementById('generate-recommendations');
        const originalText = btn.innerHTML;

        // 로딩 상태 표시
        btn.innerHTML = '<span class="loading-spinner"></span> 생성 중...';
        btn.disabled = true;

        try {
            const response = await fetch('/api/generate_recommendations', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const result = await response.json();

            if (result.success) {
                this.showNotification('추천 번호가 성공적으로 생성되었습니다!', 'success');
                setTimeout(() => {
                    location.reload();
                }, 1500);
            } else {
                this.showNotification(result.message || '추천 번호 생성에 실패했습니다.', 'error');
            }
        } catch (error) {
            console.error('Error generating recommendations:', error);
            this.showNotification('네트워크 오류가 발생했습니다.', 'error');
        } finally {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    }

    showNotification(message, type = 'info') {
        // 기존 알림 제거
        const existingNotification = document.querySelector('.notification');
        if (existingNotification) {
            existingNotification.remove();
        }

        // 새 알림 생성
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-message">${message}</span>
                <button class="notification-close">&times;</button>
            </div>
        `;

        // 스타일 추가
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#6366f1'};
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            z-index: 1000;
            transform: translateX(100%);
            transition: transform 0.3s ease;
            max-width: 300px;
        `;

        document.body.appendChild(notification);

        // 애니메이션
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
        }, 100);

        // 닫기 버튼 이벤트
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.addEventListener('click', () => {
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => notification.remove(), 300);
        });

        // 자동 제거
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.transform = 'translateX(100%)';
                setTimeout(() => notification.remove(), 300);
            }
        }, 5000);
    }

    setupAutoRefresh() {
        // 5분마다 자동 새로고침 (선택적)
        const autoRefreshToggle = document.getElementById('auto-refresh-toggle');
        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.startAutoRefresh();
                } else {
                    this.stopAutoRefresh();
                }
            });
        }
    }

    startAutoRefresh() {
        this.autoRefreshInterval = setInterval(() => {
            this.showNotification('데이터를 새로고침합니다...', 'info');
            setTimeout(() => location.reload(), 1000);
        }, 5 * 60 * 1000); // 5분
    }

    stopAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
    }

    // 통계 차트 생성 (향후 확장용)
    createCharts() {
        // Chart.js 등을 사용한 차트 생성 로직
        console.log('Charts functionality ready for implementation');
    }

    // 번호 분석 도구 (향후 확장용)
    analyzeNumbers(numbers) {
        const analysis = {
            sum: numbers.reduce((a, b) => a + b, 0),
            average: numbers.reduce((a, b) => a + b, 0) / numbers.length,
            range: Math.max(...numbers) - Math.min(...numbers),
            evenCount: numbers.filter(n => n % 2 === 0).length,
            oddCount: numbers.filter(n => n % 2 === 1).length
        };

        return analysis;
    }
}

// 페이지 로드 시 앱 초기화
document.addEventListener('DOMContentLoaded', () => {
    new LottoApp();
});

// 서비스 워커 등록 (PWA 지원)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => {
                console.log('SW registered: ', registration);
            })
            .catch(registrationError => {
                console.log('SW registration failed: ', registrationError);
            });
    });
}
