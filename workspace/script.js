// ================================
// Modern Dark Portfolio - Scripts
// ================================

document.addEventListener('DOMContentLoaded', () => {
    initNavigationProgress();
    initNavigation();
    initMobileMenu();
    initScrollEffects();
    initSkillTabs();
    initSkillBars();
    initProjectFilter();
    initProjectCards();
    initProjectsStats();
    initContactForm();
    initFadeAnimations();
    initTypewriter();
    initBackToTop();
    initSmoothScroll();
});

// ================================
// Navigation Progress Bar
// ================================

function initNavigationProgress() {
    const progressBar = document.querySelector('.nav-progress-bar');
    
    window.addEventListener('scroll', () => {
        const scrollTop = window.scrollY;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const scrollPercent = (scrollTop / docHeight) * 100;
        progressBar.style.width = `${scrollPercent}%`;
    });
}

// ================================
// Navigation
// ================================

function initNavigation() {
    const navbar = document.querySelector('.navbar');
    const navLinks = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('section[id]');

    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }

        let current = '';
        const scrollY = window.scrollY;

        sections.forEach(section => {
            const sectionTop = section.offsetTop - 150;
            const sectionHeight = section.clientHeight;

            if (scrollY >= sectionTop && scrollY < sectionTop + sectionHeight) {
                current = section.getAttribute('id');
            }
        });

        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === `#${current}`) {
                link.classList.add('active');
            }
        });
    });
}

// ================================
// Smooth Scroll
// ================================

function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const target = document.querySelector(targetId);
            
            if (target) {
                const targetPosition = target.offsetTop - 100;
                const startPosition = window.pageYOffset;
                const distance = targetPosition - startPosition;
                const duration = 1000;
                let startTime = null;

                function animation(currentTime) {
                    if (startTime === null) startTime = currentTime;
                    const timeElapsed = currentTime - startTime;
                    const run = ease(timeElapsed, startPosition, distance, duration);
                    
                    window.scrollTo(0, run);
                    
                    if (timeElapsed < duration) {
                        requestAnimationFrame(animation);
                    }
                }

                function ease(t, b, c, d) {
                    t /= d / 2;
                    if (t < 1) return c / 2 * t * t + b;
                    t--;
                    return -c / 2 * (t * (t - 2) - 1) + b;
                }

                requestAnimationFrame(animation);
            }
        });
    });
}

// ================================
// Mobile Menu
// ================================

function initMobileMenu() {
    const menuBtn = document.querySelector('.mobile-menu-btn');
    const navLinks = document.querySelector('.nav-links');

    menuBtn.addEventListener('click', () => {
        menuBtn.classList.toggle('active');
        navLinks.classList.toggle('active');
        document.body.classList.toggle('menu-open');
    });

    document.querySelectorAll('.nav-links a').forEach(link => {
        link.addEventListener('click', () => {
            menuBtn.classList.remove('active');
            navLinks.classList.remove('active');
            document.body.classList.remove('menu-open');
        });
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.navbar') && !e.target.closest('.mobile-menu-btn')) {
            menuBtn.classList.remove('active');
            navLinks.classList.remove('active');
            document.body.classList.remove('menu-open');
        }
    });

    // Close menu on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            menuBtn.classList.remove('active');
            navLinks.classList.remove('active');
            document.body.classList.remove('menu-open');
        }
    });
}

// ================================
// Scroll Effects
// ================================

function initScrollEffects() {
    const scrollIndicator = document.querySelector('.scroll-indicator');
    
    window.addEventListener('scroll', () => {
        if (window.scrollY > 200) {
            scrollIndicator.style.opacity = '0';
        } else {
            scrollIndicator.style.opacity = '1';
        }
    });
}

// ================================
// Back to Top Button
// ================================

function initBackToTop() {
    const backToTop = document.querySelector('.back-to-top');
    
    window.addEventListener('scroll', () => {
        if (window.scrollY > 500) {
            backToTop.classList.add('visible');
        } else {
            backToTop.classList.remove('visible');
        }
    });

    backToTop.addEventListener('click', () => {
        const startPosition = window.pageYOffset;
        const duration = 800;
        let startTime = null;

        function animation(currentTime) {
            if (startTime === null) startTime = currentTime;
            const timeElapsed = currentTime - startTime;
            const run = easeOutCubic(timeElapsed, startPosition, -startPosition, duration);
            
            window.scrollTo(0, run);
            
            if (timeElapsed < duration) {
                requestAnimationFrame(animation);
            }
        }

        function easeOutCubic(t, b, c, d) {
            t /= d;
            t--;
            return c * (t * t * t + 1) + b;
        }

        requestAnimationFrame(animation);
    });
}

// ================================
// Skill Tabs
// ================================

function initSkillTabs() {
    const tabs = document.querySelectorAll('.skill-tab');
    const categories = document.querySelectorAll('.skill-category');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const category = tab.dataset.category;

            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            if (category === 'all') {
                categories.forEach(cat => {
                    cat.style.display = 'block';
                    cat.classList.add('active');
                });
            } else {
                categories.forEach(cat => {
                    if (cat.dataset.category === category) {
                        cat.style.display = 'block';
                        cat.classList.add('active');
                    } else {
                        cat.style.display = 'none';
                        cat.classList.remove('active');
                    }
                });
            }

            setTimeout(() => {
                animateVisibleSkillBars();
            }, 100);
        });
    });
}

// ================================
// Skill Bars Animation
// ================================

function initSkillBars() {
    setTimeout(() => {
        animateVisibleSkillBars();
    }, 300);

    const skillsSection = document.querySelector('.skills');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                setTimeout(() => {
                    animateVisibleSkillBars();
                }, 200);
            }
        });
    }, { threshold: 0.2 });

    if (skillsSection) {
        observer.observe(skillsSection);
    }
}

function animateVisibleSkillBars() {
    const skillCards = document.querySelectorAll('.skill-category.active .skill-card');
    
    skillCards.forEach((card, index) => {
        const progressBar = card.querySelector('.skill-progress');
        if (progressBar && parseFloat(progressBar.style.width) === 0) {
            setTimeout(() => {
                const progress = progressBar.dataset.progress;
                progressBar.style.width = `${progress}%`;
            }, index * 100);
        }
    });
}

// ================================
// Project Filter
// ================================

function initProjectFilter() {
    const filterBtns = document.querySelectorAll('.filter-btn');
    const projectCards = document.querySelectorAll('.project-card');

    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const filter = btn.dataset.filter;

            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            projectCards.forEach((card, index) => {
                const category = card.dataset.category;
                
                if (filter === 'all' || category === filter) {
                    card.classList.remove('hidden');
                    card.style.animation = 'none';
                    card.offsetHeight;
                    card.style.animation = `fadeInUp 0.6s ease ${index * 0.1}s forwards`;
                } else {
                    card.classList.add('hidden');
                }
            });
        });
    });
}

// ================================
// Project Cards Animation
// ================================

function initProjectCards() {
    const projectCards = document.querySelectorAll('.project-card');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                setTimeout(() => {
                    entry.target.classList.add('visible');
                }, index * 100);
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });

    projectCards.forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
        observer.observe(card);
    });
}

// ================================
// Projects Stats Counter
// ================================

function initProjectsStats() {
    const statsSection = document.querySelector('.projects-stats');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCounters();
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.3 });

    if (statsSection) {
        observer.observe(statsSection);
    }
}

function animateCounters() {
    const counters = document.querySelectorAll('.stat-number');
    
    counters.forEach(counter => {
        const target = parseInt(counter.dataset.count);
        if (!target) return;
        
        const duration = 2000;
        const increment = target / (duration / 16);
        let current = 0;
        
        const updateCounter = () => {
            if (current < target) {
                current += increment;
                counter.textContent = Math.ceil(current);
                requestAnimationFrame(updateCounter);
            } else {
                counter.textContent = target;
            }
        };
        
        updateCounter();
    });
}

// ================================
// Contact Form
// ================================

function initContactForm() {
    const form = document.getElementById('contactForm');
    if (!form) return;
    
    const submitBtn = form.querySelector('.btn-submit');
    const messageTextarea = form.querySelector('#message');
    const charCount = form.querySelector('#charCount');
    const nameInput = form.querySelector('#name');
    const emailInput = form.querySelector('#email');
    const subjectInput = form.querySelector('#subject');
    const budgetSelect = form.querySelector('#budget');

    // Character counter for message
    messageTextarea.addEventListener('input', () => {
        const length = messageTextarea.value.length;
        charCount.textContent = length;
        
        if (length > 500) {
            charCount.style.color = '#ef4444';
        } else {
            charCount.style.color = '';
        }
    });

    // Auto-generate subject based on subject type
    const subjectTypes = form.querySelectorAll('input[name="subject_type"]');
    subjectTypes.forEach(radio => {
        radio.addEventListener('change', () => {
            const type = radio.value;
            const currentSubject = subjectInput.value;
            
            if (!currentSubject || currentSubject.startsWith('New Project') || 
                currentSubject.startsWith('Freelance') || currentSubject.startsWith('Consulting') ||
                currentSubject.startsWith('Other')) {
                const subjects = {
                    'project': 'New Project Inquiry',
                    'freelance': 'Freelance Opportunity',
                    'consulting': 'Consulting Request',
                    'other': 'General Inquiry'
                };
                subjectInput.placeholder = `${subjects[type]} - Website Redesign`;
            }
        });
    });

    // Form validation visual feedback
    const inputs = [nameInput, emailInput, messageTextarea];
    inputs.forEach(input => {
        input.addEventListener('blur', () => {
            validateInput(input);
        });
        
        input.addEventListener('input', () => {
            if (input.classList.contains('invalid')) {
                validateInput(input);
            }
        });
    });

    function validateInput(input) {
        if (input.required && !input.value.trim()) {
            input.classList.add('invalid');
            input.classList.remove('valid');
        } else if (input.type === 'email' && input.value) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (emailRegex.test(input.value)) {
                input.classList.remove('invalid');
                input.classList.add('valid');
            } else {
                input.classList.add('invalid');
                input.classList.remove('valid');
            }
        } else if (input.value.trim()) {
            input.classList.remove('invalid');
            input.classList.add('valid');
        }
    }

    // Form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        let isValid = true;
        inputs.forEach(input => {
            if (!validateInput(input)) {
                if (input.required && !input.value.trim()) {
                    isValid = false;
                }
            }
        });

        if (!isValid) {
            submitBtn.style.animation = 'shake 0.5s ease';
            setTimeout(() => {
                submitBtn.style.animation = '';
            }, 500);
            return;
        }
        
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);
        
        const originalContent = submitBtn.innerHTML;
        submitBtn.innerHTML = '<span>Sending...</span><i class="fas fa-spinner fa-spin"></i>';
        submitBtn.disabled = true;
        
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        submitBtn.innerHTML = '<span>Message Sent!</span><i class="fas fa-check"></i>';
        submitBtn.style.background = 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)';
        
        console.log('Form submitted:', data);
        
        form.reset();
        charCount.textContent = '0';
        
        inputs.forEach(input => {
            input.classList.remove('valid', 'invalid');
        });
        
        subjectInput.placeholder = 'Project Inquiry - Website Redesign';
        
        setTimeout(() => {
            submitBtn.innerHTML = originalContent;
            submitBtn.disabled = false;
            submitBtn.style.background = '';
        }, 3000);
    });
}

// Add shake animation
const style = document.createElement('style');
style.textContent = `
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
        20%, 40%, 60%, 80% { transform: translateX(5px); }
    }
`;
document.head.appendChild(style);

// ================================
// Fade In Animations
// ================================

function initFadeAnimations() {
    const fadeElements = document.querySelectorAll('.section-header, .about-content, .contact-info, .contact-form');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

    fadeElements.forEach(el => observer.observe(el));
}

// ================================
// Typewriter Effect
// ================================

function initTypewriter() {
    const typewriterElement = document.querySelector('.typewriter');
    if (!typewriterElement) return;

    const texts = [
        'Full Stack Developer',
        'UI/UX Designer',
        'Problem Solver',
        'Tech Enthusiast'
    ];
    
    let textIndex = 0;
    let charIndex = 0;
    let isDeleting = false;
    let typeSpeed = 100;

    function type() {
        const currentText = texts[textIndex];
        
        if (isDeleting) {
            typewriterElement.textContent = currentText.substring(0, charIndex - 1);
            charIndex--;
            typeSpeed = 50;
        } else {
            typewriterElement.textContent = currentText.substring(0, charIndex + 1);
            charIndex++;
            typeSpeed = 100;
        }

        if (!isDeleting && charIndex === currentText.length) {
            typeSpeed = 2000;
            isDeleting = true;
        } else if (isDeleting && charIndex === 0) {
            isDeleting = false;
            textIndex = (textIndex + 1) % texts.length;
            typeSpeed = 500;
        }

        setTimeout(type, typeSpeed);
    }

    type();
}

// ================================
// Parallax Effect for Background Orbs
// ================================

window.addEventListener('scroll', () => {
    const scrollY = window.scrollY;
    const orbs = document.querySelectorAll('.bg-orb');
    
    orbs.forEach((orb, index) => {
        const speed = (index + 1) * 0.05;
        orb.style.transform = `translateY(${scrollY * speed}px)`;
    });
});

// ================================
// Keyboard Navigation Support
// ================================

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const menuBtn = document.querySelector('.mobile-menu-btn');
        const navLinks = document.querySelector('.nav-links');
        menuBtn.classList.remove('active');
        navLinks.classList.remove('active');
        document.body.classList.remove('menu-open');
    }
});
