const header=document.querySelector(".header");
const menuToggle=document.getElementById("menuToggle");
const navLinks=document.getElementById("navLinks");

window.addEventListener("scroll",()=>{
    header.classList.toggle("scrolled",window.scrollY>20);
});

menuToggle.addEventListener("click",()=>{
    navLinks.classList.toggle("active");
    menuToggle.textContent=navLinks.classList.contains("active")?"✕":"☰";
});

document.querySelectorAll(".nav-links a").forEach(link=>{
    link.addEventListener("click",()=>{
        navLinks.classList.remove("active");
        menuToggle.textContent="☰";
    });
});

const slides=document.querySelectorAll(".slide");
const dots=document.querySelectorAll(".dot");
const prevButton=document.getElementById("prevSlide");
const nextButton=document.getElementById("nextSlide");
let currentSlide=0;
let sliderInterval;

function showSlide(index){
    slides.forEach(slide=>slide.classList.remove("active"));
    dots.forEach(dot=>dot.classList.remove("active"));
    currentSlide=(index+slides.length)%slides.length;
    slides[currentSlide].classList.add("active");
    dots[currentSlide].classList.add("active");
}

function nextSlide(){
    showSlide(currentSlide+1);
}

function startSlider(){
    clearInterval(sliderInterval);
    sliderInterval=setInterval(nextSlide,3500);
}

nextButton.addEventListener("click",()=>{
    nextSlide();
    startSlider();
});

prevButton.addEventListener("click",()=>{
    showSlide(currentSlide-1);
    startSlider();
});

dots.forEach(dot=>{
    dot.addEventListener("click",()=>{
        showSlide(Number(dot.dataset.slide));
        startSlider();
    });
});

startSlider();

const revealElements=document.querySelectorAll(".reveal");

const revealObserver=new IntersectionObserver(entries=>{
    entries.forEach(entry=>{
        if(entry.isIntersecting){
            entry.target.classList.add("show");
            revealObserver.unobserve(entry.target);
        }
    });
},{
    threshold:.12
});

revealElements.forEach(element=>{
    revealObserver.observe(element);
});