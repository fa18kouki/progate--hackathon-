var TMamMicRec = function (
    control,
    micOnBtn,
    recStartBtn,
    recStopBtn,
    recMime
  ) {
    this.control = control;
    this.micOnBtn = micOnBtn;
    this.recStartBtn = recStartBtn;
    this.recStopBtn = recStopBtn;
    this.recMime = recMime;
  
    this.stream = null;
    this.mediaRecorder = null;
    this.chunks = [];
    this.recStartBtn.setAttribute("disabled", true);
    this.recStopBtn.setAttribute("disabled", true);
    this.type = null;
  
    this.micOnBtn.addEventListener(
      "click",
      function () {
        if (navigator.mediaDevices == undefined) {
          alert("未対応ブラウザ 又は HTTPS接続していません");
          return;
        }
        navigator.mediaDevices
          .getUserMedia({ audio: true })
          .then(
            function (stream) {
              this.stream = stream;
  
              this.mediaRecorder = new MediaRecorder(this.stream);
              this.mediaRecorder.addEventListener(
                "dataavailable",
                function (event) {
                  this.chunks.push(event.data);
                  console.log(event.data);
                }.bind(this)
              );
              this.mediaRecorder.addEventListener(
                "stop",
                function () {
                  this.type = this.chunks[0].type;
                  this.recMime.innerHTML = this.type;
                  let blob = new Blob(this.chunks, { type: this.type });
                  this.chunks = [];
              
                  // Blob を Data URI に変換して送信
                  let reader = new FileReader();
                  reader.readAsDataURL(blob);
                  reader.onloadend = function() {
                    let base64data = reader.result;
                    let formData = new FormData();
                    formData.append("record", base64data);
              
                    fetch("/audio_file_upload/", {
                      method: "POST",
                      body: formData,
                    })
                    .then((response) => response.json())
                    .then((data) => console.log("Success:", data))
                    .catch((error) => console.error("Error:", error));
                  }
                }.bind(this)
              );
              this.recStartBtn.removeAttribute("disabled");
              this.micOnBtn.setAttribute("disabled", true);
            }.bind(this)
          )
          .catch(
            function (e) {
              console.log(e);
              document.getElementById("alert").innerHTML = e;
            }.bind(this)
          );
      }.bind(this)
    );
    this.recStartBtn.addEventListener(
      "click",
      function () {
        this.recStartBtn.setAttribute("disabled", true);
        this.recStopBtn.removeAttribute("disabled");
        this.mediaRecorder.start();
      }.bind(this)
    );
    this.recStopBtn.addEventListener(
      "click",
      function () {
        this.mediaRecorder.stop();
      }.bind(this)
    );
  };
  
  window.addEventListener("DOMContentLoaded", function () {
    mamMicRec = new TMamMicRec(
      document.getElementById("Control"),
      document.getElementById("MicOn"),
      document.getElementById("RecStart"),
      document.getElementById("RecStop"),
      document.getElementById("RecMime")
    );
  });
  