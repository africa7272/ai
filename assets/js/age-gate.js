(function(){
  var KEY = "age_ok";
  function isOk(){
    return localStorage.getItem(KEY)==="1" || document.cookie.indexOf(KEY+"=1")>-1;
  }
  function allow(){
    try{ localStorage.setItem(KEY,"1"); }catch(e){}
    document.cookie = KEY+"=1; path=/; max-age="+(60*60*24*30);
    var g=document.getElementById("ageGate"); if(g) g.classList.add("hidden");
  }
  function deny(){
    window.location.href = "/";
  }
  window.ageGateAllow = allow;
  window.ageGateDeny = deny;
  document.addEventListener("DOMContentLoaded", function(){
    var g=document.getElementById("ageGate");
    if(!isOk()){ if(g) g.classList.remove("hidden"); }
  });
})();
