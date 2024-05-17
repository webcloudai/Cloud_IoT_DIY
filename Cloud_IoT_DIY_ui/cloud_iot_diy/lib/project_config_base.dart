/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License 
*/
class ProjectConfig {
  // AUTHORIZATION PARAMS
  static String authorizeUrl =
      'Your services authorization url'; //Your service's authorization url
  static String tokenUrl = 'Your services token url'; //Your service's token url
  static String revokeUrl =
      'Your services revoke url (optional)'; //Your service's revoke url (optional)
  // Client authorization params
  static String resourceServerId = "your website domain"; // project_subdomain
  static String clientId = "your client id";
  static String clientSecret = "your client secret";
  // API PARAMS
  static String devicesEndpoint = "url of your devices endpoint";
  static String dashboardsEndpoint = "url of your dashboards endpoint";
  // Extra default values
  static String defaultRole = "name if the the role";

  //
  // METHODS
  static String getDeviceIds() {
    return ProjectConfig.devicesEndpoint;
  }

  static String getDeviceEndpoints(String deviceId) {
    return '${ProjectConfig.devicesEndpoint}/$deviceId?endpointsList';
  }

  static String getDataEndpoint(
      String deviceId, String dataType, String dataPoint, String dataFormat) {
    return '${ProjectConfig.devicesEndpoint}/$deviceId/$dataType?values=$dataPoint&format=$dataFormat';
  }

  static String getDashboardsList() {
    // return ProjectConfig.devicesEndpoint;
    return ProjectConfig.dashboardsEndpoint;
  }

  static String getDashboard(String dashboardId) {
    // return ProjectConfig.devicesEndpoint;
    return '${ProjectConfig.dashboardsEndpoint}/$dashboardId';
  }
}
