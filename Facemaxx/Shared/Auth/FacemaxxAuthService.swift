import AuthenticationServices
import CryptoKit
import Foundation
import Security
import SwiftUI
import UIKit

enum FacemaxxAuthProvider: String, Codable {
    case guest
    case google
    case apple

    var titleKey: LocalizedStringKey {
        switch self {
        case .guest:
            "onboarding.auth.provider.guest"
        case .google:
            "onboarding.auth.provider.google"
        case .apple:
            "onboarding.auth.provider.apple"
        }
    }
}

struct FacemaxxAuthSession: Codable, Equatable {
    let provider: FacemaxxAuthProvider
    let accessToken: String?
    let refreshToken: String?
    let expiresAt: Date?
    let userID: String?
    let email: String?
    let displayName: String?

    static let guest = FacemaxxAuthSession(
        provider: .guest,
        accessToken: nil,
        refreshToken: nil,
        expiresAt: nil,
        userID: FacemaxxInstallIdentity.currentID.uuidString,
        email: nil,
        displayName: nil
    )
}

@MainActor
final class FacemaxxAuthService: ObservableObject {
    static let shared = FacemaxxAuthService()

    @Published private(set) var session: FacemaxxAuthSession?
    @Published private(set) var isAuthenticating = false

    private let presentationProvider = WebAuthPresentationContextProvider()
    private var webAuthenticationSession: ASWebAuthenticationSession?
    private var appleRawNonce: String?

    private init() {
        let storedSession = FacemaxxAuthSessionStore.load()
        if storedSession?.provider == .guest {
            FacemaxxAuthSessionStore.clear()
            session = nil
        } else {
            session = storedSession
        }
    }

    func signInAsGuest() {
        save(FacemaxxAuthSession.guest)
    }

    func signOut() {
        FacemaxxAuthSessionStore.clear()
        session = nil
    }

    func validAccessToken(forceRefresh: Bool = false) async -> String? {
        guard let currentSession = session ?? FacemaxxAuthSessionStore.load(),
              currentSession.provider != .guest,
              let accessToken = currentSession.accessToken,
              !accessToken.isEmpty else {
            return nil
        }

        if !forceRefresh,
           let expiresAt = currentSession.expiresAt,
           expiresAt.timeIntervalSinceNow > 90 {
            return accessToken
        }

        guard let refreshToken = currentSession.refreshToken,
              !refreshToken.isEmpty else {
            return forceRefresh ? nil : accessToken
        }

        do {
            let refreshed = try await refreshSession(currentSession, refreshToken: refreshToken)
            save(refreshed)
            return refreshed.accessToken
        } catch {
            print("Facemaxx auth token refresh failed: \(error.localizedDescription)")
            return forceRefresh ? nil : accessToken
        }
    }

    func signInWithGoogle() async throws {
        let config = try SupabaseAuthConfiguration.current()
        let authorizeURL = try config.oauthAuthorizeURL(provider: "google")

        isAuthenticating = true
        defer { isAuthenticating = false }

        let callbackURL = try await startWebAuthentication(url: authorizeURL, callbackScheme: config.callbackScheme)
        let response = try SupabaseAuthResponse(callbackURL: callbackURL)
        save(response.session(provider: .google))
    }

    func configureAppleRequest(_ request: ASAuthorizationAppleIDRequest) {
        let rawNonce = Self.randomNonceString()
        appleRawNonce = rawNonce

        request.requestedScopes = [.fullName, .email]
        request.nonce = Self.sha256(rawNonce)
    }

    func signInWithApple(_ result: Result<ASAuthorization, Error>) async throws {
        let authorization = try result.get()
        guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential else {
            throw FacemaxxAuthError.invalidAppleCredential
        }

        guard let tokenData = credential.identityToken,
              let identityToken = String(data: tokenData, encoding: .utf8) else {
            throw FacemaxxAuthError.missingAppleIdentityToken
        }

        let config = try SupabaseAuthConfiguration.current()
        isAuthenticating = true
        defer { isAuthenticating = false }

        let fullName = credential.fullName.map { PersonNameComponentsFormatter().string(from: $0) }
        let response = try await exchangeIDToken(
            config: config,
            provider: "apple",
            identityToken: identityToken,
            nonce: appleRawNonce,
            email: credential.email,
            displayName: fullName
        )
        save(response.session(provider: .apple, displayName: fullName))
    }

    private func save(_ session: FacemaxxAuthSession) {
        FacemaxxAuthSessionStore.save(session)
        self.session = session
    }

    private func startWebAuthentication(url: URL, callbackScheme: String) async throws -> URL {
        try await withCheckedThrowingContinuation { continuation in
            let authSession = ASWebAuthenticationSession(url: url, callbackURLScheme: callbackScheme) { callbackURL, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                guard let callbackURL else {
                    continuation.resume(throwing: FacemaxxAuthError.missingOAuthCallback)
                    return
                }

                continuation.resume(returning: callbackURL)
            }

            authSession.presentationContextProvider = presentationProvider
            authSession.prefersEphemeralWebBrowserSession = true
            webAuthenticationSession = authSession

            if !authSession.start() {
                continuation.resume(throwing: FacemaxxAuthError.failedToStartOAuth)
            }
        }
    }

    private func exchangeIDToken(
        config: SupabaseAuthConfiguration,
        provider: String,
        identityToken: String,
        nonce: String?,
        email: String?,
        displayName: String?
    ) async throws -> SupabaseAuthResponse {
        var components = URLComponents(
            url: config.supabaseURL.appendingPathComponent("auth/v1/token"),
            resolvingAgainstBaseURL: false
        )
        components?.queryItems = [URLQueryItem(name: "grant_type", value: "id_token")]

        guard let url = components?.url else {
            throw FacemaxxAuthError.invalidSupabaseURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(config.anonKey, forHTTPHeaderField: "apikey")
        request.setValue("Bearer \(config.anonKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(
            SupabaseIDTokenRequest(
                provider: provider,
                idToken: identityToken,
                nonce: nonce,
                email: email,
                name: displayName
            )
        )

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw FacemaxxAuthError.invalidSupabaseResponse
        }

        guard (200..<300).contains(httpResponse.statusCode) else {
            let body = String(data: data, encoding: .utf8)
            throw FacemaxxAuthError.supabaseAuthFailed(statusCode: httpResponse.statusCode, body: body)
        }

        return try JSONDecoder().decode(SupabaseAuthResponse.self, from: data)
    }

    private func refreshSession(_ currentSession: FacemaxxAuthSession, refreshToken: String) async throws -> FacemaxxAuthSession {
        let config = try SupabaseAuthConfiguration.current()
        var components = URLComponents(
            url: config.supabaseURL.appendingPathComponent("auth/v1/token"),
            resolvingAgainstBaseURL: false
        )
        components?.queryItems = [URLQueryItem(name: "grant_type", value: "refresh_token")]

        guard let url = components?.url else {
            throw FacemaxxAuthError.invalidSupabaseURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(config.anonKey, forHTTPHeaderField: "apikey")
        request.setValue("Bearer \(config.anonKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(SupabaseRefreshTokenRequest(refreshToken: refreshToken))

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw FacemaxxAuthError.invalidSupabaseResponse
        }

        guard (200..<300).contains(httpResponse.statusCode) else {
            let body = String(data: data, encoding: .utf8)
            throw FacemaxxAuthError.supabaseAuthFailed(statusCode: httpResponse.statusCode, body: body)
        }

        let authResponse = try JSONDecoder().decode(SupabaseAuthResponse.self, from: data)
        return authResponse.session(preserving: currentSession)
    }

    private static func randomNonceString(length: Int = 32) -> String {
        precondition(length > 0)
        let charset = Array("0123456789ABCDEFGHIJKLMNOPQRSTUVXYZabcdefghijklmnopqrstuvwxyz-._")
        var result = ""
        var remainingLength = length

        while remainingLength > 0 {
            var randoms = [UInt8](repeating: 0, count: 16)
            let status = SecRandomCopyBytes(kSecRandomDefault, randoms.count, &randoms)
            if status != errSecSuccess {
                fatalError("Unable to generate secure random bytes for Sign in with Apple.")
            }

            for random in randoms where remainingLength > 0 {
                if random < charset.count {
                    result.append(charset[Int(random)])
                    remainingLength -= 1
                }
            }
        }

        return result
    }

    private static func sha256(_ input: String) -> String {
        let inputData = Data(input.utf8)
        let hashedData = SHA256.hash(data: inputData)
        return hashedData.map { String(format: "%02x", $0) }.joined()
    }
}

enum FacemaxxAuthSessionStore {
    private static let service = "com.facemaxx.auth"
    private static let account = "session"

    static var currentAccessToken: String? {
        load()?.accessToken
    }

    static func save(_ session: FacemaxxAuthSession) {
        guard let data = try? JSONEncoder().encode(session) else { return }

        clear()

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        ]
        SecItemAdd(query as CFDictionary, nil)
    }

    static func load() -> FacemaxxAuthSession? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess,
              let data = item as? Data else {
            return nil
        }

        return try? JSONDecoder().decode(FacemaxxAuthSession.self, from: data)
    }

    static func clear() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
        SecItemDelete(query as CFDictionary)
    }
}

private struct SupabaseAuthConfiguration {
    let supabaseURL: URL
    let anonKey: String
    let callbackScheme: String

    static func current() throws -> SupabaseAuthConfiguration {
        let bundle = Bundle.main
        let rawURL = bundle.object(forInfoDictionaryKey: "FacemaxxSupabaseURL") as? String
        let rawAnonKey = bundle.object(forInfoDictionaryKey: "FacemaxxSupabaseAnonKey") as? String
        let rawCallbackScheme = bundle.object(forInfoDictionaryKey: "FacemaxxAuthCallbackScheme") as? String

        guard let rawURL,
              let url = URL(string: rawURL),
              !rawURL.isEmpty,
              !rawURL.contains("$(") else {
            throw FacemaxxAuthError.missingSupabaseURL
        }

        guard let rawAnonKey,
              !rawAnonKey.isEmpty,
              !rawAnonKey.contains("$(") else {
            throw FacemaxxAuthError.missingSupabaseAnonKey
        }

        let callbackScheme = (rawCallbackScheme?.isEmpty == false ? rawCallbackScheme : "facemaxx") ?? "facemaxx"
        return SupabaseAuthConfiguration(supabaseURL: url, anonKey: rawAnonKey, callbackScheme: callbackScheme)
    }

    func oauthAuthorizeURL(provider: String) throws -> URL {
        var components = URLComponents(
            url: supabaseURL.appendingPathComponent("auth/v1/authorize"),
            resolvingAgainstBaseURL: false
        )
        components?.queryItems = [
            URLQueryItem(name: "provider", value: provider),
            URLQueryItem(name: "redirect_to", value: "\(callbackScheme)://auth/callback"),
            URLQueryItem(name: "scopes", value: "openid profile email")
        ]

        guard let url = components?.url else {
            throw FacemaxxAuthError.invalidSupabaseURL
        }
        return url
    }
}

private struct SupabaseIDTokenRequest: Encodable {
    let provider: String
    let idToken: String
    let nonce: String?
    let email: String?
    let name: String?

    enum CodingKeys: String, CodingKey {
        case provider
        case idToken = "id_token"
        case nonce
        case email
        case name
    }
}

private struct SupabaseRefreshTokenRequest: Encodable {
    let refreshToken: String

    enum CodingKeys: String, CodingKey {
        case refreshToken = "refresh_token"
    }
}

private struct SupabaseAuthResponse: Decodable {
    let accessToken: String
    let refreshToken: String?
    let expiresIn: Int?
    let user: SupabaseAuthUser?

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case expiresIn = "expires_in"
        case user
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        accessToken = try container.decode(String.self, forKey: .accessToken)
        refreshToken = try container.decodeIfPresent(String.self, forKey: .refreshToken)
        expiresIn = try container.decodeIfPresent(Int.self, forKey: .expiresIn)
        user = try container.decodeIfPresent(SupabaseAuthUser.self, forKey: .user)
    }

    init(callbackURL: URL) throws {
        let values = callbackURL.queryAndFragmentParameters
        if let errorDescription = values["error_description"] ?? values["error"] {
            throw FacemaxxAuthError.oauthFailed(errorDescription)
        }

        if values["code"] != nil, values["access_token"] == nil {
            throw FacemaxxAuthError.oauthCodeExchangeUnavailable
        }

        guard let accessToken = values["access_token"], !accessToken.isEmpty else {
            throw FacemaxxAuthError.missingOAuthAccessToken
        }

        self.accessToken = accessToken
        self.refreshToken = values["refresh_token"]
        self.expiresIn = values["expires_in"].flatMap(Int.init)
        self.user = nil
    }

    func session(provider: FacemaxxAuthProvider, displayName: String? = nil) -> FacemaxxAuthSession {
        FacemaxxAuthSession(
            provider: provider,
            accessToken: accessToken,
            refreshToken: refreshToken,
            expiresAt: expiresIn.map { Date().addingTimeInterval(TimeInterval($0)) },
            userID: user?.id,
            email: user?.email,
            displayName: displayName
        )
    }

    func session(preserving currentSession: FacemaxxAuthSession) -> FacemaxxAuthSession {
        FacemaxxAuthSession(
            provider: currentSession.provider,
            accessToken: accessToken,
            refreshToken: refreshToken ?? currentSession.refreshToken,
            expiresAt: expiresIn.map { Date().addingTimeInterval(TimeInterval($0)) },
            userID: user?.id ?? currentSession.userID,
            email: user?.email ?? currentSession.email,
            displayName: currentSession.displayName
        )
    }
}

private struct SupabaseAuthUser: Decodable {
    let id: String?
    let email: String?
}

private enum FacemaxxAuthError: LocalizedError {
    case missingSupabaseURL
    case missingSupabaseAnonKey
    case invalidSupabaseURL
    case invalidSupabaseResponse
    case failedToStartOAuth
    case missingOAuthCallback
    case missingOAuthAccessToken
    case oauthCodeExchangeUnavailable
    case oauthFailed(String)
    case invalidAppleCredential
    case missingAppleIdentityToken
    case supabaseAuthFailed(statusCode: Int, body: String?)

    var errorDescription: String? {
        switch self {
        case .missingSupabaseURL:
            "SUPABASE_URL is not configured in the Facemaxx target build settings."
        case .missingSupabaseAnonKey:
            "SUPABASE_ANON_KEY is not configured in the Facemaxx target build settings."
        case .invalidSupabaseURL:
            "Supabase auth URL could not be built."
        case .invalidSupabaseResponse:
            "Supabase returned an invalid auth response."
        case .failedToStartOAuth:
            "The OAuth login session could not be started."
        case .missingOAuthCallback:
            "OAuth did not return a callback URL."
        case .missingOAuthAccessToken:
            "OAuth callback did not include an access token."
        case .oauthCodeExchangeUnavailable:
            "OAuth returned a code-only callback. Enable the Facemaxx redirect URL in Supabase or use the Supabase Swift SDK PKCE flow."
        case let .oauthFailed(message):
            message
        case .invalidAppleCredential:
            "Apple did not return a valid credential."
        case .missingAppleIdentityToken:
            "Apple did not return an identity token."
        case let .supabaseAuthFailed(statusCode, body):
            "Supabase auth failed (\(statusCode)): \(body ?? "No response body")"
        }
    }
}

private final class WebAuthPresentationContextProvider: NSObject, ASWebAuthenticationPresentationContextProviding {
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        let foregroundScene = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .first { $0.activationState == .foregroundActive }

        return foregroundScene?.windows.first { $0.isKeyWindow } ?? ASPresentationAnchor()
    }
}

private extension URL {
    var queryAndFragmentParameters: [String: String] {
        var values = [String: String]()

        if let queryItems = URLComponents(url: self, resolvingAgainstBaseURL: false)?.queryItems {
            for item in queryItems {
                values[item.name] = item.value
            }
        }

        if let fragment,
           let fragmentComponents = URLComponents(string: "facemaxx://auth/callback?\(fragment)"),
           let fragmentItems = fragmentComponents.queryItems {
            for item in fragmentItems {
                values[item.name] = item.value
            }
        }

        return values
    }
}
