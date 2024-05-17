/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License 
*/
import 'package:flutter/material.dart';
import 'package:oauth2_client/oauth2_client.dart';
import 'package:oauth2_client/access_token_response.dart';
import 'custom_oauth2_client.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

import 'project_config_other.dart'
    if (dart.library.html) 'project_config_html.dart'
    if (dart.library.io) 'project_config_io.dart' as multi_platform_config;
import 'project_config_base.dart';

class AuthenticationProvider with ChangeNotifier {
  bool _isAuthenticated = false;
  AccessTokenResponse? _authResp;
  String? _accessToken;
  String? _refreshToken;
  String? _role;
  List<String>? _availableDevices;
  List<String>? _availableDashboards;
  String? _currentDashboard;
  final OAuth2Client _oauth2Client = CustomOAuth2Client(
    redirectUri:
        multi_platform_config.ProjectConfigPlatformSpecific.redirectUri,
    customUriScheme:
        multi_platform_config.ProjectConfigPlatformSpecific.customUriScheme,
  );
  // GETTERS
  bool get isAuthenticated => _isAuthenticated;
  String? get accessToken => _accessToken;
  String? get role => _role;
  AccessTokenResponse? get authResp => _authResp;

  Future<String> getAccessToken() async {
    if (_authResp == null) return 'null';
    if (_authResp != null &&
        _refreshToken != null &&
        _authResp!.isExpired() &&
        _authResp!.hasRefreshToken()) {
      AccessTokenResponse? refreshResp = await _oauth2Client.refreshToken(
        _refreshToken!,
        clientId: ProjectConfig.clientId,
        clientSecret: ProjectConfig.clientSecret,
        scopes: [
          "openid",
          "${ProjectConfig.resourceServerId}/${multi_platform_config.ProjectConfigPlatformSpecific.scope}"
        ],
      );
      if (refreshResp.error != null && refreshResp.accessToken != null) {
        _authResp = refreshResp;
        _accessToken = _authResp!.accessToken;
        _refreshToken = _authResp!.refreshToken;
      }
    }
    return "${_accessToken ?? ''}=";
  }

  /// collect available dashboards, devices and current dashboard
  Future<Map<String, List<String>>> getPreliminaryData(
      bool forceRefresh) async {
    // if (_availableDevices != null &&
    //     _availableDevices!.isNotEmpty &&
    //     !forceRefresh) return _availableDevices!;
    List<String> awaitedDashboards = await getAvailableDashboards(forceRefresh);
    Map<String, List<String>> result = {
      "devices": await getAvailableDevices(forceRefresh),
      "dashboards": awaitedDashboards,
      "current_dashboard": [_currentDashboard ?? ""],
    };
    return result;
  }

  Future<List<String>> getAvailableDevices(bool forceRefresh) async {
    if (_availableDevices != null &&
        _availableDevices!.isNotEmpty &&
        !forceRefresh) return _availableDevices!;
    String accessToken = await getAccessToken();
    http.Response? response;
    try {
      response = await http.get(Uri.parse(ProjectConfig.getDeviceIds()),
          headers: {
            "Authorization": "Bearer $accessToken",
            "Content-Type": "application/json"
          });
    } catch (e) {
      print(e.toString());
      response = null;
    }
    if (response != null && response.statusCode == 200) {
      print("---data collected---");
      print(response.body);
      try {
        _availableDevices = (json.decode(response.body) as List)
            .map((item) => item as String)
            .toList();
      } catch (e) {
        print(e.toString());
        _availableDevices = [];
      }
      return _availableDevices!;
    } else {
      throw Exception('Failed to load data');
    }
  }

  /// Collect dashboard names available for this user from API
  Future<List<String>> getAvailableDashboards(bool forceRefresh) async {
    if (_availableDashboards != null &&
        _availableDashboards!.isNotEmpty &&
        !forceRefresh) return _availableDashboards!;
    String accessToken = await getAccessToken();
    http.Response? response;
    try {
      response = await http.get(Uri.parse(ProjectConfig.getDashboardsList()),
          headers: {
            "Authorization": "Bearer $accessToken",
            "Content-Type": "application/json"
          });
    } catch (e) {
      print(e.toString());
      response = null;
    }
    if (response != null && response.statusCode == 200) {
      print("---data collected---");
      print(response.body);
      List<String> allAvailableDashboards = [];
      try {
        allAvailableDashboards = (json.decode(response.body) as List)
            .map((item) => Uri.decodeComponent(item as String))
            .toList();
      } catch (e) {
        print(e.toString());
        allAvailableDashboards = [];
      }
      // check if we have "current" in the list of dashboard
      _availableDashboards = [];
      for (String oneDashboardName in allAvailableDashboards) {
        if (oneDashboardName.contains("current/")) {
          _currentDashboard = oneDashboardName;
        } else {
          _availableDashboards!.add(oneDashboardName);
        }
      }
      return _availableDashboards!;
    } else {
      throw Exception('Failed to load data');
    }
  }

  Future<void> logIn() async {
    try {
      // print("--------->Will call getTokenWithAuthCodeFlow");
      _authResp = await _oauth2Client.getTokenWithAuthCodeFlow(
        clientId: ProjectConfig.clientId,
        clientSecret: ProjectConfig.clientSecret,
        scopes: [
          "openid",
          "${ProjectConfig.resourceServerId}/${multi_platform_config.ProjectConfigPlatformSpecific.scope}"
        ],
      );
      // print("--------->Resp getTokenWithAuthCodeFlow");
      // print(_authResp);

      if (_authResp!.error == null) {
        _accessToken = _authResp!.accessToken;
        _refreshToken = _authResp!.refreshToken;
        if (_accessToken != null) {
          print(_accessToken);
          // _role = resp..accessTokenClaims?['role'];  // Assumes 'role' claim exists in your token
          _role = ProjectConfig.defaultRole;
          _isAuthenticated = true;
        } else {
          print("No error BUT NO TOKEN");
          _role = null;
          _isAuthenticated = false;
        }
      } else {
        // Handle the case when we have an error
        // print("=== ERROR ===");
        // print(_authResp!.error);
        // print(_authResp!.errorDescription);

        _role = null;
        _isAuthenticated = false;
      }
    } catch (e) {
      // Handle the error
      // print("=== EXCEPTION ===");
      // print(e);
      _role = null;
      _isAuthenticated = false;
    }
    notifyListeners();
  }

  void logOut() {
    _isAuthenticated = false;
    _accessToken = null;
    _role = null;
    notifyListeners();
  }
}
