export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-3xl font-semibold">Privacy Policy</h1>

      <div className="mt-6 space-y-4 text-muted-foreground">
        <p>
          Peach uses authentication provided by Amazon Cognito and Google OAuth.
        </p>

        <p>
          We use basic account information such as your email address and, when
          signing in with Google, your name to identify you in the application.
        </p>

        <p>
          Peach does not sell or share your personal information for advertising
          purposes.
        </p>
      </div>
    </main>
  );
}
