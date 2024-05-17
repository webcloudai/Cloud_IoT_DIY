/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License 
*/
import 'project_config_base.dart';

class ProjectConfigPlatformSpecific extends ProjectConfig {
  static String get scope => "webapp"; //web_app_scope
  // comment out these lines if you'll need to run your application locally (debug mode)
  static String redirectUri =
      "https://<your web-site domain>/callback.html"; // CLOUD config
  // Uncomment these lines if you'll need to run your application locally (debug mode)
  // static String get redirectUri =>
  //     "http://localhost:63756/callback.html"; // LOCAL debugging config !
  static String get customUriScheme => "";
}
