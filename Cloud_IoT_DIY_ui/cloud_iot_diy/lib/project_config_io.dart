/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License 
*/
import 'project_config_base.dart';

class ProjectConfigPlatformSpecific extends ProjectConfig {
  static String get customUriScheme => "iotdiy"; // io_uri_scheme
  static String get scope => "mobileapp"; //mobile_app_scope
  static String get redirectUri =>
      "iotdiy://iotdiy.webcloudai.com/callback"; // io_callback
}
