function rebind_cb() {
    var xhr = new XMLHttpRequest();
    xhr.onreadystatechange = function() {
      if (xhr.readyState == 4) {
          alert(xhr.responseText);
      }
    }
    var path = getParameterByName('path');
    if (path == "") {
      path = '/'
    }
    xhr.open("GET",path,false);
    xhr.send();
}
