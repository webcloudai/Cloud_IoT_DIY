/*
© 2022 Daniil Sokolov (daniil.sokolov@webcloudai.com)
MIT License 
*/
import 'package:oauth2_client/oauth2_client.dart';
import 'project_config_base.dart';

class CustomOAuth2Client extends OAuth2Client {
  CustomOAuth2Client({
    required String redirectUri,
    required String customUriScheme,
  }) : super(
          authorizeUrl:
              ProjectConfig.authorizeUrl, //Your service's authorization url
          tokenUrl: ProjectConfig.tokenUrl, //Your service's token url
          revokeUrl:
              ProjectConfig.revokeUrl, //Your service's revoke url (optional)
          redirectUri: redirectUri,
          customUriScheme: customUriScheme,
        );
}
