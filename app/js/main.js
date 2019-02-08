angular
  .module("premailer", ["hljs", "door3.css"])

  // .config(function (hljsServiceProvider) {
  //   hljsServiceProvider.setOptions({
  //     // replace tab with 4 spaces
  //     tabReplace: '    '
  //   });
  // })

  .filter("filesize", function() {
    return function humanFileSize(bytes, precision) {
      "use strict";
      var units = ["bytes", "Kb", "Mb", "Gb", "Tb", "Pb"];

      if (isNaN(parseFloat(bytes)) || !isFinite(bytes)) {
        return "?";
      }

      var unit = 0;

      while (bytes >= 1024) {
        bytes /= 1024;
        unit++;
      }

      return bytes.toFixed(+precision) + " " + units[unit];
    };
  })

  // from http://uncorkedstudios.com/blog/multipartformdata-file-upload-with-angularjs
  .directive("fileModel", [
    "$parse",
    function($parse) {
      return {
        restrict: "A",
        link: function(scope, element, attrs) {
          var model = $parse(attrs.fileModel);
          var modelSetter = model.assign;

          element.bind("change", function() {
            scope.$apply(function() {
              modelSetter(scope, element[0].files[0]);
            });
          });
        }
      };
    }
  ])

  // .directive("fileread", [function () {
  //     return {
  //         scope: {
  //             fileread: "="
  //         },
  //         link: function (scope, element, attributes) {
  //             element.bind("change", function (changeEvent) {
  //                 var reader = new FileReader();
  //                 reader.onload = function (loadEvent) {
  //                     scope.$apply(function () {
  //                         scope.fileread = loadEvent.target.result;
  //                     });
  //                 }
  //                 reader.readAsDataURL(changeEvent.target.files[0]);
  //             });
  //         }
  //     }
  // }])

  .controller("ConversionCtrl", function($scope, $http, $timeout, $css) {
    $css.add(
      "//maxcdn.bootstrapcdn.com/font-awesome/4.3.0/css/font-awesome.min.css"
    );
    if (/#(upload|url|textarea)/.test(document.location.hash)) {
      $scope.active = document.location.hash.substring(
        1,
        document.location.hash.length
      );
    } else {
      $scope.active = "textarea";
    }
    $scope.advancedMode = false;
    $scope.activeResult = "html";
    $scope.results = null;
    $scope.showWarnings = false;
    $scope.conversion = {
      // the things that are supposed to be true by default
      preserve_inline_attachments: true,
      exclude_pseudoclasses: true,
      strip_important: true,
      method: "html",
      cache_css_parsing: true,
      align_floating_images: true,
      remove_unset_properties: true,
      allow_network: true
    };
    $scope.conversion.html =
      "<html>\n<style>\np { color:red }\n</style>\n" +
      "<body>\n  <p>Text</p>\n</body>\n</html>";

    $scope.toggleShowWarnings = function() {
      $scope.showWarnings = !$scope.showWarnings;
    };

    $scope.countWarnings = function(warnings) {
      return (warnings.match(/\n/g) || []).length;
    };

    // http://heyjavascript.com/4-creative-ways-to-clone-objects/
    function cloneObject(obj) {
      if (obj === null || typeof obj !== "object") {
        return obj;
      }
      var temp = obj.constructor(); // give temp the original obj's constructor
      for (var key in obj) {
        temp[key] = cloneObject(obj[key]);
      }
      return temp;
    }

    function tidyConversionData(data) {
      data = cloneObject(data);
      var splits = ["external_styles", "disable_basic_attributes"];
      splits.forEach(function(key) {
        if (data[key]) {
          data[key] = data[key].split(/\s*\n+\s*/);
        }
      });
      return data;
    }

    $scope.start = function(start) {
      start = start || false;
      $scope.converting = true;
      $scope.results = null;
      $scope.conversionErrors = [];
      $scope.serverError = null;
      if (!start && $scope.active === "upload") {
        // Need to read that file into a string.
        // The reason for using a DOM selector like this is that it works
        // even between reloads since the browser remembers what was selected
        // before. With angular that gets forgotten.
        var fileInput = document.querySelector('input[type="file"]');
        var file = fileInput.files[0];
        var reader = new FileReader();
        reader.onload = function(data) {
          $scope.conversion.html = data.target.result;
          $scope.start(true);
        };
        reader.readAsText(file);
      } else {
        if ($scope.conversion.url && $scope.active !== "url") {
          $scope.conversion.url = "";
        } else if ($scope.conversion.url && !$scope.conversion.base_url) {
          $scope.conversion.base_url = $scope.conversion.url;
        }
        $http
          .post("/api/transform", tidyConversionData($scope.conversion))
          .success(function(response) {
            if (response.errors) {
              $scope.conversionErrors = response.errors;
            } else {
              $scope.results = response;
              $timeout(function() {
                document.getElementById("results").scrollIntoView();
              }, 100);
            }
          })
          .error(function() {
            $scope.serverError = arguments[0];
            console.error.apply(console, arguments);
          })
          .finally(function() {
            $scope.converting = false;
          });
      }
    };

    $scope.setActiveResult = function(value) {
      $scope.activeResult = value;
      if (value === "preview") {
        var d = document.querySelector("iframe").contentWindow.document;
        d.open();
        d.write($scope.results.html);
        d.close();
      }
    };

    $scope.removeConversionError = function(error) {
      $scope.conversionErrors.splice($scope.conversionErrors.indexOf(error), 1);
    };
  });
