angular.module('premailer', ['hljs'])

// .config(function (hljsServiceProvider) {
//   hljsServiceProvider.setOptions({
//     // replace tab with 4 spaces
//     tabReplace: '    '
//   });
// })




.filter('filesize', function() {
  return function humanFileSize(bytes, precision) {
    'use strict';
    var units = [
      'bytes',
      'Kb',
      'Mb',
      'Gb',
      'Tb',
      'Pb'
    ];

    if (isNaN(parseFloat(bytes)) || !isFinite(bytes)) {
      return '?';
    }

    var unit = 0;

    while (bytes >= 1024) {
      bytes /= 1024;
      unit++;
    }

    return bytes.toFixed(+precision) + ' ' + units[unit];
  };
})

.controller('ConversionCtrl', function($scope, $http, $timeout) {
  $scope.results = null;
  $scope.showWarnings = false;
  $scope.conversion = {};
  $scope.conversion.html = '<html>\n<style>\np { color:red }</style>\n' +
    '<body><p>Text</p>\n</body></html>';

  $scope.toggleShowWarnings = function() {
    $scope.showWarnings = !$scope.showWarnings;
  };

  $scope.countWarnings = function(warnings) {
    return (warnings.match(/\n/g) || []).length;
  };

  $scope.start = function() {
    $scope.converting = true;
    $scope.results = null;
    $scope.conversionErrors = [];
    $http.post('/api/transform', $scope.conversion)
    .success(function(response) {
      if (response.errors) {
        $scope.conversionErrors = response.errors;
      } else {
        $scope.results = response;
        $timeout(function() {
          document.getElementById('results').scrollIntoView();
        }, 100);
      }
    })
    .error(function() {
      console.error.apply(console, arguments);
    })
    .finally(function() {
      $scope.converting = false;
    });
  };

  $scope.removeConversionError = function(error) {
    $scope.conversionErrors.splice($scope.conversionErrors.indexOf(error), 1);
  };

})
;
