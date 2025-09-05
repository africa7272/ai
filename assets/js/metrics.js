(function () {
  var ID = 103658483;
  var w = window, d = document, SRC = "https://mc.yandex.ru/metrika/tag.js?id=" + ID;
  if (w.ym && w.ym.a) return; // уже есть
  (function(m,e,t,r,i,k,a){
    m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
    m[i].l=1*new Date();
    for (var j=0;j<e.scripts.length;j++){ if(e.scripts[j].src===r){ return; } }
    k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a);
  })(w,d,"script",SRC,"ym");
  w.ym(ID,"init",{ ssr:true, webvisor:true, clickmap:true, ecommerce:"dataLayer", accurateTrackBounce:true, trackLinks:true });
})();
